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
        'ai_helper.py',
        'bot.py',
        'catalog.py',
        'catalog_manager.py',
        'image_analyzer.py',
        'error_manager.py',
        'user_memory.py',
        'excel_manager.py',
        'data/video_catalog.json',
        'data/screen_errors.json'
    ]
    
    for filename in files_to_upload:
        local_path = os.path.join(os.path.dirname(__file__), filename)
        remote_path = f"{remote_dir}/{filename}"
        print(f"Uploading {filename} -> {remote_path}...")
        sftp.put(local_path, remote_path)
        print(f"Uploaded {filename} successfully.")
        
    sftp.close()
    
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
