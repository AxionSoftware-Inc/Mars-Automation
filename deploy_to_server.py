import os
import io
import time
import tarfile
import paramiko

def deploy():
    hostname = '169.58.123.200'
    username = 'root'
    password = 'LEGIONGAMING'
    remote_dir = '/root/mars-bot'

    print(f"Connecting to {hostname} via SSH...")
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(hostname, username=username, password=password, timeout=15)
    print("SSH Connected successfully!")

    files_to_sync = [
        'requirements.txt',
        'bot.py',
        'admin_manager.py',
        'openrouter_client.py',
        'ai_helper.py',
        'user_memory.py',
        'ofd_bridge.py',
        'ofd_client.py',
        'transaction_tracker.py',
        'receipt_analyzer.py',
        'image_analyzer.py',
        'excel_manager.py',
        'error_manager.py',
        'state_manager.py',
        'translit_manager.py',
        'payment_accounts.py',
        'ARCHITECTURE.md',
        'handlers/__init__.py',
        'handlers/chat.py',
        'handlers/media.py',
        'handlers/debt.py',
        'handlers/commands.py',
        'handlers/channel.py',
        'handlers/admin.py',
        'handlers/intents/__init__.py',
        'handlers/intents/billing.py',
        'handlers/intents/hardware.py',
        'handlers/intents/conversation.py',
        'handlers/intents/operator.py',
        'handlers/intents/mxik.py',
        'core/__init__.py',
        'core/models.py',
        'core/engine.py',
        'core/rule_engine.py',
        'core/module_registry.py',
        'core/group_responder.py',
        'modules/__init__.py',
        'modules/admin_module.py',
        'data/custom_patches.json',
        'data/regional_admins.json',
        'data/admin_config.json',
        'data/bot_state.json'
    ]

    print("Building compressed tar archive in memory...")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for rel_path in files_to_sync:
            local_p = os.path.join(os.path.dirname(__file__), rel_path)
            if os.path.exists(local_p):
                tar.add(local_p, arcname=rel_path)
                print(f"  + Added: {rel_path}")
            else:
                print(f"  ! Skipped missing: {rel_path}")

    tar_bytes = buf.getvalue()
    print(f"Archive size: {len(tar_bytes)} bytes. Uploading via SFTP to server...")

    sftp = ssh.open_sftp()
    remote_tar = f"{remote_dir}/deploy_mars.tar.gz"
    sftp.putfo(io.BytesIO(tar_bytes), remote_tar)
    sftp.close()
    print(f"Archive uploaded to {remote_tar}")

    # Remote papkalarni yaratish va tar ochish
    ssh.exec_command(f"mkdir -p {remote_dir}/handlers/intents {remote_dir}/core {remote_dir}/modules {remote_dir}/data")
    _, stdout, stderr = ssh.exec_command(f"tar -xzf {remote_tar} -C {remote_dir} && rm -f {remote_tar}")
    exit_status = stdout.channel.recv_exit_status()
    err_msg = stderr.read().decode().strip()
    if exit_status != 0:
        print(f"Tar extraction failed: {err_msg}")
        ssh.close()
        return
    print("Files successfully unpacked on remote server!")

    print("\nEnsuring dependencies (httpx, pypdf, Pillow) on remote server...")
    _, stdout, stderr = ssh.exec_command(f"{remote_dir}/venv/bin/pip install httpx pypdf Pillow")
    pip_status = stdout.channel.recv_exit_status()
    print(f"Pip install status: {pip_status}")

    print("\nClearing stale escalation locks in user_sessions.json on server...")
    clear_cmd = (
        f"{remote_dir}/venv/bin/python -c \""
        f"import json, os; p='{remote_dir}/data/user_sessions.json'; "
        f"d=json.load(open(p)) if os.path.exists(p) else {{}}; "
        f"[v.update({{'is_escalated_to_admin': False, 'escalation_repeats': 0}}) for v in d.values() if isinstance(v, dict)]; "
        f"json.dump(d, open(p, 'w'), ensure_ascii=False, indent=2) if os.path.exists(p) else None\""
    )
    _, stdout, _ = ssh.exec_command(clear_cmd)
    stdout.channel.recv_exit_status()

    print("\nRestarting mars-bot.service...")
    _, stdout, stderr = ssh.exec_command("systemctl restart mars-bot.service")
    status = stdout.channel.recv_exit_status()
    print(f"Service restart status: {status}")

    time.sleep(2)

    print("\nChecking service state...")
    _, stdout, _ = ssh.exec_command("systemctl is-active mars-bot.service")
    active_status = stdout.read().decode().strip()
    print(f"Service active status: {active_status}")

    print("\nRecent service logs:")
    _, stdout, _ = ssh.exec_command("journalctl -u mars-bot.service -n 25 --no-pager")
    print(stdout.read().decode())

    ssh.close()
    print("\n🚀 Serverga to'liq muvaffaqiyatli deploy qilindi!")

if __name__ == "__main__":
    deploy()
