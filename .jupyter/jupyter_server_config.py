try:
    import os
    import json
    import traceback
    import pgcontents
    
    # Import password function from correct location
    try:
        from jupyter_server.auth import passwd as hash_passwd
    except ImportError:
        try:
            from notebook.auth import passwd as hash_passwd
        except ImportError:
            from IPython.lib.security import passwd as hash_passwd

    c = get_config()

    # Root directory for notebook
    c.ServerApp.root_dir='/'

    ### Password protection ###
    # http://jupyter-notebook.readthedocs.io/en/latest/security.html
    if os.environ.get('JUPYTER_NOTEBOOK_PASSWORD_DISABLED') != 'DangerZone!':
        passwd = os.environ['JUPYTER_NOTEBOOK_PASSWORD']
        c.ServerApp.password = hash_passwd(passwd)
    else:
        c.ServerApp.token = ''
        c.ServerApp.password = ''

    ### Make it so the default shell is bash & the prompt is not awful:
    c.ServerApp.terminado_settings = {'shell_command': ['/bin/bash']}

    ### PostresContentsManager ###
    database_url = os.getenv('DATABASE_URL', None)
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    if database_url:
        # Tell IPython to use PostgresContentsManager for all storage.
        c.ServerApp.contents_manager_class = pgcontents.PostgresContentsManager

        # Set the url for the database used to store files.  See
        # http://docs.sqlalchemy.org/en/rel_0_9/core/engines.html#postgresql
        # for more info on db url formatting.
        c.PostgresContentsManager.db_url = database_url

        # PGContents associates each running notebook server with a user, allowing
        # multiple users to connect to the same database without trampling each other's
        # notebooks. By default, we use the result of result of getpass.getuser(), but
        # a username can be specified manually like so:
        c.PostgresContentsManager.user_id = 'heroku'

        # Load notebooks into pgcontents
        try:
            import glob
            from jupyter_server.services.contents.filemanager import FileContentsManager

            notebooks_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'notebooks'))
            notebook_files = glob.glob(os.path.join(notebooks_dir, '*.ipynb'))

            if notebook_files:
                # Reuse the existing PostgresContentsManager configuration
                manager = pgcontents.PostgresContentsManager(
                    db_url=database_url,
                    user_id='heroku'
                )
                manager.file_manager = FileContentsManager()

                for nb_path in notebook_files:
                    nb_name = os.path.basename(nb_path)
                    jupyter_path = f'/{nb_name}'
                    try:
                        with open(nb_path, 'r', encoding='utf-8') as f:
                            file_content = f.read()
                        
                        # Validate that the content is valid JSON (for notebooks)
                        if nb_path.endswith('.ipynb'):
                            import json
                            json.loads(file_content)  # Validate JSON format
                        
                        file_model = {
                            'type': 'file',
                            'content': file_content,
                            'format': 'text',
                        }
                        
                        # Check if file already exists and update it
                        try:
                            existing = manager.get(jupyter_path)
                            print(f"Notebook {nb_name} already exists, updating with latest content")
                            # Save will update the existing file
                            manager.save(model=file_model, path=jupyter_path)
                            print(f"Successfully updated {nb_name} at {jupyter_path}")
                        except Exception:
                            # File doesn't exist, create new
                            manager.save(model=file_model, path=jupyter_path)
                            print(f"Successfully uploaded new {nb_name} to {jupyter_path}")
                        
                    except json.JSONDecodeError as e:
                        print(f"Invalid JSON in notebook {nb_path}: {e}")
                    except Exception as e:
                        print(f"Error uploading {nb_path} to {jupyter_path}: {e}")
            else:
                print("No notebook files found in notebooks directory")
                
        except ImportError as e:
            print(f"Required modules not available for notebook loading: {e}")
        except Exception as e:
            print(f"Error during notebook loading: {e}")

        # Set a maximum file size, if desired.
        #c.PostgresContentsManager.max_file_size_bytes = 1000000 # 1MB File cap

except Exception:
    traceback.print_exc()
    # if an exception occues, notebook normally would get started
    # without password set. For security reasons, execution is stopped.
    exit(-1)
