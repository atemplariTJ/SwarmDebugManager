from backend.settings import Settings


def test_ssh_configured_requires_user_and_password():
    assert Settings(ssh_user="robot", ssh_password="robot").ssh_configured is True
    assert Settings(ssh_user="robot", ssh_password="").ssh_configured is False
    assert Settings(ssh_user="", ssh_password="robot").ssh_configured is False
