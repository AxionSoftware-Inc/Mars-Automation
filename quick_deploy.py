import os
import time
import paramiko

def quick_deploy():
    hostname = '169.58.123.200'
    username = 'root'
    password = 'LEGIONGAMING'
    remote_dir = '/root/mars-bot'

    print(f"Connecting to {hostname}...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, username=username, password=password, timeout=15, banner_timeout=30)
    print("SSH Connected!")

    files_to_sync = [
        'requirements.txt',
        'openrouter_client.py',
        'ai_helper.py',
        'user_memory.py',
        'ofd_bridge.py',
        'payment_accounts.py',
        'ARCHITECTURE.md',
        'handlers/chat.py',
        'handlers/media.py',
        'handlers/intents/billing.py',
        'handlers/intents/hardware.py',
        'handlers/intents/conversation.py',
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

    print("\nInstalling/verifying httpx on server...")
    _, stdout, stderr = ssh.exec_command(f"{remote_dir}/venv/bin/pip install httpx")
    status = stdout.channel.recv_exit_status()
    print(f"Pip status: {status}")

    print("\nRestarting mars-bot.service...")
    _, stdout, stderr = ssh.exec_command("systemctl restart mars-bot.service")
    status = stdout.channel.recv_exit_status()
    print(f"Restart exit status: {status}")

    time.sleep(2)
    print("\nChecking service status...")
    _, stdout, stderr = ssh.exec_command("systemctl is-active mars-bot.service")
    active_status = stdout.read().decode().strip()
    print(f"Service state: {active_status}")

    _, stdout, stderr = ssh.exec_command("journalctl -u mars-bot.service -n 15 --no-pager")
    logs = stdout.read().decode()
    print(f"\nRecent logs:\n{logs}")

    ssh.close()
    print("\nQuick deploy completed successfully!")

if __name__ == "__main__":
    quick_deploy()
