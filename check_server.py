import paramiko
import sys

def run():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect('169.58.123.200', username='root', password='LEGIONGAMING', timeout=10)
    
    commands = [
        "ls -la /root/mars-bot",
        "systemctl list-units --type=service | grep -i mars || true",
        "ps aux | grep -i bot.py | grep -v grep || true"
    ]
    
    for cmd in commands:
        print(f"=== Command: {cmd} ===")
        stdin, stdout, stderr = client.exec_command(cmd, timeout=10)
        print(stdout.read().decode('utf-8'))
        err = stderr.read().decode('utf-8')
        if err:
            print("STDERR:", err)
            
    client.close()

if __name__ == "__main__":
    run()
