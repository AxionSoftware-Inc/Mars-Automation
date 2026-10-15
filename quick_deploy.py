import os
import paramiko

def quick_deploy():
    hostname = '169.58.123.200'
    username = 'root'
    password = 'LEGIONGAMING'
    remote_dir = '/root/mars-bot'

    print(f"Connecting to {hostname}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, username=username, password=password, timeout=10)
    print("SSH Connected!")

    files_to_sync = [
        'ai_helper.py',
        'openrouter_client.py',
        'user_memory.py',
        'handlers/media.py',
        'handlers/intents/billing.py',
        'payment_accounts.py',
        'handlers/intents/operator.py'
    ]

    sftp = ssh.open_sftp()
    for f in files_to_sync:
        local_p = os.path.join(os.path.dirname(__file__), f)
        remote_p = f"{remote_dir}/{f}"
        print(f"Uploading {f} -> {remote_p}...")
        sftp.put(local_p, remote_p)
        print(f"Uploaded {f} OK")
    sftp.close()

    print("Restarting mars-bot.service...")
    _, stdout, stderr = ssh.exec_command("systemctl restart mars-bot.service")
    status = stdout.channel.recv_exit_status()
    print(f"Restart exit status: {status}")

    print("Checking service status...")
    _, stdout, stderr = ssh.exec_command("systemctl is-active mars-bot.service")
    active_status = stdout.read().decode().strip()
    print(f"Service state: {active_status}")

    _, stdout, stderr = ssh.exec_command("journalctl -u mars-bot.service -n 10 --no-pager")
    logs = stdout.read().decode()
    print(f"Recent logs:\n{logs}")

    ssh.close()
    print("Quick deploy completed successfully!")

if __name__ == "__main__":
    quick_deploy()
