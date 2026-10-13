import os
import paramiko

def deploy():
    hostname = '169.58.123.200'
    username = 'root'
    password = 'LEGIONGAMING'
    remote_dir = '/root/mars-bot'
    
    print(f"Connecting to {hostname}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, username=username, password=password, timeout=15)
    
    sftp = ssh.open_sftp()
    
    files_to_upload = [
        '.env',
        'requirements.txt',
        'openrouter_client.py',
        'ai_helper.py',
        'bot.py',
        'catalog.py',
        'catalog_manager.py',
        'image_analyzer.py',
        'receipt_analyzer.py',
        'admin_manager.py',
        'error_manager.py',
        'user_memory.py',
        'excel_manager.py',
        'payment_accounts.py',
        'translit_manager.py',
        'ofd_bridge.py',
        'transaction_tracker.py',
        'state_manager.py',
        'ARCHITECTURE.md',
        'README.md',
        'data/video_catalog.json',
        'data/screen_errors.json',
        'data/admin_config.json',
        'core/__init__.py',
        'core/models.py',
        'core/engine.py',
        'core/rule_engine.py',
        'data/custom_patches.json',
        'handlers/__init__.py',
        'handlers/admin.py',
        'handlers/channel.py',
        'handlers/chat.py',
        'handlers/commands.py',
        'handlers/debt.py',
        'handlers/media.py',
        'test_4_stage_pipeline_and_fiscal_check.py'
    ]
    
    # Ensure handlers and core directories exist on remote server
    try:
        sftp.mkdir(f"{remote_dir}/handlers")
    except Exception:
        pass

    try:
        sftp.mkdir(f"{remote_dir}/core")
    except Exception:
        pass

    try:
        sftp.mkdir(f"{remote_dir}/data")
    except Exception:
        pass

    for filename in files_to_upload:
        local_path = os.path.join(os.path.dirname(__file__), filename)
        remote_path = f"{remote_dir}/{filename}"
        print(f"Uploading {filename} -> {remote_path}...")
        sftp.put(local_path, remote_path)
        print(f"Uploaded {filename} successfully.")
        
    sftp.close()

    print("\nEnsuring dependencies (pypdf) on remote server...")
    stdin, stdout, stderr = ssh.exec_command(f"{remote_dir}/venv/bin/pip install pypdf")
    stdout.channel.recv_exit_status()
    
    print("\nRestarting mars-bot.service...")
    stdin, stdout, stderr = ssh.exec_command("systemctl restart mars-bot.service")
    stdout.channel.recv_exit_status()
    
    print("\nChecking service status...")
    stdin, stdout, stderr = ssh.exec_command("systemctl status mars-bot.service --no-pager")
    print(stdout.read().decode('utf-8'))
    
    print("\nRecent service logs:")
    stdin, stdout, stderr = ssh.exec_command("journalctl -u mars-bot.service -n 25 --no-pager")
    print(stdout.read().decode('utf-8'))
    
    ssh.close()
    print("Deployment completed successfully!")

if __name__ == "__main__":
    deploy()
