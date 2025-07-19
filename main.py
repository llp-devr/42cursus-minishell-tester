import argparse
import colorama
import os
import pexpect
import re
import tempfile
import yaml

from colorama import Fore, Style

colorama.init(autoreset=True)

class ShellPty:
    def __init__(self, cmd, args, prompt):
        self.prompt = re.compile(re.escape(prompt))
        env = {"PATH": "/bin:/usr/bin"}
        env["USER"] = os.environ.get("USER", "unknown")
        env["HOME"] = os.environ.get("HOME", "/tmp")
        env["SHELL"] = "/bin/crashinette"
        tmp = tempfile.NamedTemporaryFile(delete=False)
        env["TMPFILE"] = tmp.name
        self.tempfile = tmp.name
        self.child = pexpect.spawn(cmd, args=args, encoding="utf-8", env=env)
        self.child.setwinsize(30, 60)
        self.child.expect(self.prompt)
        self.last_exit_status = None

    def exec(self, command):
        output = ""

        # COMMAND
        self.child.sendline(command)
        self.child.expect("\n")
        if len(command) > 40:
            output += f"crashinette>> {command[:40]}...\n"
        else:
            output += f"crashinette>> {command}\n"

        # OUTPUT
        self.child.expect(self.prompt)
        output += f"{self.child.before}"

        # EXIT CODE
        self.child.sendline("echo $?")
        self.child.expect(self.prompt)
        output += f"crashinette>> {self.child.before}"

        return output

    def close(self):
        output = "\n\n"
        self.child.sendline("exit 0")
        self.child.expect(pexpect.EOF)
        output += "EXIT REPORT:\n"
        output += f"{self.child.before}"
        output += "\n\n"
        output += f"Exit status: {self.child.exitstatus}"
        return output

def assert_equals(output1, output2, tmpfile1, tmpfile2):
    lines1 = output1.strip().splitlines()
    lines2 = output2.strip().splitlines()

    lines1 = [line.expandtabs(8) for line in lines1]
    lines2 = [line.expandtabs(8) for line in lines2]

    max_len = max(len(lines1), len(lines2))
    lines1 += [""] * (max_len - len(lines1))
    lines2 += [""] * (max_len - len(lines2))

    success = True

    for l1, l2 in zip(lines1, lines2):
        if l1 == l2:
            color = Fore.GREEN
        elif l1.replace("minishell", "crashinette").replace("bash", "crashinette").replace(tmpfile1, "/tmp/crashinette").replace(tmpfile2, "/tmp/crashinette"
        ) == l2.replace("minishell", "crashinette").replace("bash", "crashinette").replace(tmpfile1, "/tmp/crashinette").replace(tmpfile2, "/tmp/crashinette"):
            color = Fore.MAGENTA
        else:
            color = Fore.RED
            success = False
        print(f"{color}|{l1:<60}|{l2:<60}|")

    return success


def banner():
    print("")
    print(f"{Fore.GREEN}|{'Minishell':<60}|{'Bash':<60}|")


def main():
    parser = argparse.ArgumentParser(description="Compare minishell and bash outputs")

    parser.add_argument(
        "--minishell",
        type=str,
        required=True,
        help="Command to minishell executable",
    )

    parser.add_argument(
        "--minishell-prompt", type=str, required=True, help="Prompt of `minishell`"
    )

    parser.add_argument(
        "--bash", type=str, required=True, help="Command to bash executable"
    )

    parser.add_argument(
        "--bash-prompt", type=str, required=True, help="Prompt of `bash --posix`"
    )

    parser.add_argument("--tests", type=str, required=True, help="List of tests")

    args = parser.parse_args()

    print(f"Minishell command: {args.minishell}")
    print(f"Bash command: {args.bash}")

    bash = ShellPty(cmd=args.bash, args=["--posix"], prompt=args.bash_prompt)
    minishell = ShellPty(
    cmd="valgrind", 
    args=[
        "--quiet",
        "--tool=memcheck", 
        "--track-fds=yes",
        "--leak-check=full",
        "--show-leak-kinds=all",
        "--suppressions=minishell.suppress",
        "--error-exitcode=1",
        "--exit-on-first-error=yes",
        args.minishell
    ],
    prompt=args.minishell_prompt
)

    with open(args.tests, "r") as file:
        tests = yaml.safe_load(file)

        banner()

        for command in tests["commands"]:
            if not assert_equals(minishell.exec(command), bash.exec(command), minishell.tempfile, bash.tempfile):
                break
    
    assert_equals(minishell.close(), bash.close(), minishell.tempfile, bash.tempfile)

if __name__ == "__main__":
    main()
