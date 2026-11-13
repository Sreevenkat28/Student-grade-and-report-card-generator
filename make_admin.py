"""Run ON YOUR OWN COMPUTER to make an account the admin of this device.

    python3 make_admin.py

Creates the account if it doesn't exist (asks for email + password), then writes the
git-ignored `.admin_device` file. Only this folder on this machine gets admin access;
the deployed Streamlit app never has this file, so nobody online can be admin.
"""
import getpass
import sys

import auth


def main():
    username = input("Admin username: ").strip().lower()
    member = auth.find_member(username)
    if member is None:
        email = input("Admin email: ").strip()
        pw = getpass.getpass("Password: ")
        if pw != getpass.getpass("Confirm password: "):
            sys.exit("Passwords do not match.")
        ok, msg, email, username = auth.check_signup(email, username)
        if not ok:
            sys.exit(msg)
        err = auth.check_password(pw)
        if err:
            sys.exit(err)
        auth.create_member(email, username, pw)
        print(f"Created account '{username}'.")
    else:
        username = member[0]
    with open(auth.ADMIN_FILE, "w") as f:
        f.write(username)
    print(f"'{username}' is now the admin on this device. Run: streamlit run streamlit_app.py")


if __name__ == "__main__":
    main()
