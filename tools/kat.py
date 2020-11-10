"""
MIT License

Copyright (c) 2020 Peh Yu Xiang

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""


import argparse
import json
import sys
import pathlib
from pathlib import Path
import os
import random
import datetime as dt
import sys
import csv

import requests
import bs4
from bs4 import BeautifulSoup



###############
#  CONSTANTS  #
###############

# JSON file containing account info {"Kattis": {"user": <user>, "pass": <pass>}}
FILE_ACCOUNT = pathlib.Path("tools/pwd.json")
FOLDER_ARCHIVE = "src"
FOLDER_WORKSPACE = "stash"
FOLDER_TOOLS = "tools" #"tools"
FILE_CHROME = str(Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")) # Windows only

URL_BASE = "https://open.kattis.com/" # main page
URL_LOGIN = "https://open.kattis.com/login/email" # login page
URL_PROBLEM = "https://open.kattis.com/problems"

TARGET_LANG = "cpp"
assert TARGET_LANG in ("cpp",)  # TODO: To extend



def main():
    parser = argparse.ArgumentParser("kat")#, description="Kattis helper")
    subparsers = parser.add_subparsers(metavar="<command>", dest="command")

    parser_generate = subparsers.add_parser("get", help="retrieve problems from Kattis")
    parser_generate.add_argument("problem", nargs="+", help="problems to be downloaded, or one of { _trivial , _easy , _medium , _hard }")
    parser_submit = subparsers.add_parser("submit", help="submit problems to Kattis")
    parser_submit.add_argument("problem", nargs="+", help="problems to be submitted")
    parser_record = subparsers.add_parser("record", help="record data") # placeholder

    parser_pack = subparsers.add_parser("pack", help="pack workspace") # placeholder
    parser_stash = subparsers.add_parser("stash", help="shelve uncommitted work")
    parser_stash = subparsers.add_parser("unstash", help="get uncommitted work")
    # parser_stash.add_argument("action", metavar="action", help="one of 'push' or 'pull' stash", choices=["push", "pull"]) # similar to git's

    # TODO: Add parser_test to check file access file and auto check with output
    # OLD SCRIPT:
    # @echo off
    #
    # .\a > my_output.txt & fc my_output.txt %*
    # del /f my_output.txt
    #
    # rem Powershell: .\a > myOutput.txt | diff (cat myOutput.txt) (cat testcase1.out)
    # rem bash (macOS, Linux): ./a.out | diff - testcase1.out

    args = parser.parse_args()
    if not args.command:
        parser.parse_args(["-h"]) # nothing specified
    if args.command == "get":
        if not args.problem:
            parser.parse_args(["get", "-h"]) # nothing specified
        _get(args.problem)
    elif args.command == "submit":
        if not args.problem: parser.parse_args(["submit", "-h"])
        _submit(args.problem)
    elif args.command == "pack":
        _pack()
    elif args.command == "stash":
        _stash("push")
    elif args.command == "unstash":
        _stash("pull")
    elif args.command == "record":
        _record()


###################
#  READ PASSWORD  #
###################

SESSION = None
# Temporary (permanent) scrape from .kattisrc
with open("tools/.kattisrc") as f:
    rows = f.read().split("\n")
    for row in rows:
        if row.startswith("username:"):
            USERNAME = row.split("username: ")[-1]
            break
    else:
        raise RuntimeError("Faulty .kattisrc file!")

if USERNAME == "pyuxiang":
    raise RuntimeError("'.kattisrc' not updated with credentials - see README installation step 4.")



def _login():
    # Enforce single login attempt
    # Ought to save cookies somewhere to reuse across instances
    global SESSION
    global USERNAME
    if SESSION: return

    # Read account details
    with open(FILE_ACCOUNT) as f:
        _ = json.load(f)
        account_email = _["Kattis"]["user"]
        account_password = _["Kattis"]["pass"]
        if account_email == "ENTER YOUR EMAIL HERE":
            raise RuntimeError("'pwd.json' not updated with credentials - see README installation step 4.")
        del _

    SESSION = requests.Session()
    r = SESSION.get(URL_LOGIN)
    soup = bs4.BeautifulSoup(r.content, features="html.parser")
    token = soup.find("input", {"name": "csrf_token"}).get("value")
    data = {
        "csrf_token": token,
        "user": account_email,
        "password": account_password,
        "submit": "Submit",
    }
    r = SESSION.post(URL_LOGIN, data=data) # redirects to main page
    soup = bs4.BeautifulSoup(r.content, features="html.parser")
    username_parent = soup.find("div", {"class": "user-infobox-name"})
    USERNAME = username_parent.find("a").get("href").split("/")[-1]
    return r

def _confirm(msg="Confirm? [Y/N] ", fail_msg="Nothing changed."):
    if input(msg).upper() != "Y":
        if fail_msg: print(fail_msg)
        return False
    return True



#######################
#  RETRIEVE QUESTION  #
#######################

def _get(problems):
    # TODO: Add check for 'wkhtmltopdf' (https://wkhtmltopdf.org/)
    # wkhtmltopdf, bs4, requests dependencies
    RANDOM_KEY = ["_trivial", "_easy", "_medium", "_hard"] # random problem

    for problem in problems:

        # Retrieve random problem
        if problem in RANDOM_KEY:
            print(f"Getting random {problem[1:]} problem...")
            _login()
            r = SESSION.get(URL_BASE)
            soup = bs4.BeautifulSoup(r.content, features="html.parser")
            is_problem_url = lambda href: href and href.startswith("/problems/")
            problems = [tag.get("href").split("/")[-1] for tag in soup.findAll(href=is_problem_url)]
            problem = problems[RANDOM_KEY.index(problem)*2 + random.randint(0, 1)]

        else:
            if "_" in problem:
                print(f"Problem '{problem}' contains invalid '_'")
                continue
            if "." in problem:
                print(f"Problem '{problem}' contains invalid '.'")
                continue

        URL = f"{URL_PROBLEM}/{problem}"
        if pathlib.Path(f"{problem}.pdf").exists():
            if not _confirm(f"File '{problem}.pdf' already exists, confirm copy? [Y/N] "): exit(1)

        # Print test cases
        r = requests.get(URL)
        if r.status_code != 200:
            print(f"Invalid URL: {URL}")
            exit(1)
        soup = bs4.BeautifulSoup(r.content, "html.parser")
        code_snippets = [t.findChildren("pre") for t in soup.findAll("table", {"class": "sample"})]
        for i, (incode, outcode) in enumerate(code_snippets, 1):
            with open(f"{problem}_{i}.in", "w") as f:
                f.write(incode.text)
            with open(f"{problem}_{i}.out", "w") as f:
                f.write(outcode.text)

        # Generate template code
        DELIM = "[[INPUT LINE]]"
        if TARGET_LANG == "cpp":
            with open(f"{FOLDER_TOOLS+'/' if FOLDER_TOOLS else ''}template.cpp", "r") as f:
                template = f.read()
            index = template.find(DELIM)
            insertion = "\n".join([f'    // ifstream cin("{problem}_{i+1}.in");' for i in range(len(code_snippets))])
            template = template[:index] + insertion + template[index+len(DELIM):]
            with open(f"{problem}.cpp", "w") as f:
                f.write(template)
        else:
            print(f"No generator supported for '{TARGET_LANG}'.")

        # Print Kattis problem using wkhtmltopdf
        wkhtmltopdf_options = "-B 0 -L 0 -R 0 -T 0" # no margins
        os.system(f"{str(Path('tools/wkhtmltopdf'))} {wkhtmltopdf_options} {URL} {problem}.pdf > nul 2>&1") # TODO: make OS-independent
        print(f"Kattis problem '{problem}' successfully retrieved!")

def _submit(problems):
    # Relies on tools/.submit by Kattis
    for problem in problems:
        os.system(f"python {FOLDER_TOOLS+'/' if FOLDER_TOOLS else ''}.submit {problem}")
        if not USERNAME: _login()
        print(FILE_CHROME)
        os.system(f"\"{FILE_CHROME}\" --restore-last-session https://open.kattis.com/users/{USERNAME}/submissions/{problem.split('.')[0]}")


def _stash(command):

    # List out all existing workspaces
    work_path = pathlib.Path() / FOLDER_WORKSPACE
    work_path.mkdir(exist_ok=True)
    workspaces = list(work_path.glob("*"))
    workspaces.sort(key=str)

    if command == "push":
        num = 0 if len(workspaces) == 0 else  int(workspaces[-1].name) + 1
        des_path = work_path / str(num)
        des_path.mkdir()
        src_path = pathlib.Path()

    elif command == "pull":
        if (len(workspaces) == 0):
            print("Nothing to unstash.")
            exit(1)

        src_path = workspaces[-1]
        des_path = pathlib.Path()

    conflicts = []
    for ftype in ["cpp", "pdf", "in", "out", "py", "exe", "txt"]:
        for fp in src_path.glob("*." + ftype):
            if (fp.name.startswith("_kattis")): continue
            try:
                fp.rename(des_path / fp.name)
            except:
                conflicts.append(fp.name)

    if conflicts:
        print(f"Conflicting filenames: {conflicts}")
        print("Pull terminated.")
        exit(1)

    if command == "pull":
        src_path.rmdir()

    print(f"{command.title()} successful.")


def _pack():
    if not _confirm("Confirm clear workspace? [Y/N] "): exit(1)

    target = pathlib.Path() / FOLDER_ARCHIVE
    target.mkdir(exist_ok=True)
    for ftype in ["cpp", "pdf", "in", "out", "py"]:
        for fp in pathlib.Path().glob("*." + ftype):
            if (fp.name.startswith("_kattis")): continue
            try:
                fp.rename(target / fp)
            except:
                pass

    for ftype in ["o", "exe", "txt"]:
        for fp in pathlib.Path().glob("*." + ftype):
            fp.unlink()

    print("Workspace cleared.")

def _record():
    print("Polling Kattis data...")
    # Given Kattis problem ids, e.g. longswaps, in a newline
    # separated file, retrieve and store problem data (time, memory, etc.)
    # in a csv.

    PROB_IDS = "_kattis_prob_ids.txt"
    URL_BASE = "https://open.kattis.com/problems/"
    URL_SUBMISSION = f"https://open.kattis.com/users/{USERNAME}/submissions/"
    URL_LOGIN = "https://open.kattis.com/login/email"

    # No need to query if empty directory
    #rows = [f.split(".")[0] for f in os.listdir() if f.endswith(".cpp")]
    #rows = [fp.stem for fp in Path().absolute().parent.glob("*.cpp")]
    rows = [fp.stem for fp in Path().glob("*.cpp") if "_" not in fp.stem]
    if not rows:
        print("No files to be read.")
        with open(PROB_IDS, "w", newline="") as fout:
            fout.write("\n")
        exit(0)

    _login()

    def get(prob_id):
        r = SESSION.get(URL_BASE+prob_id)
        soup = BeautifulSoup(r.content, features="html.parser")

        title = soup.find("h1").text
        pdata = [tag.parent.text for tag in soup.findAll("strong")]
        for pdatum in pdata:
            if "Difficulty" in pdatum:
                difficulty = pdatum.split(" ")[-1]
            if "CPU Time limit" in pdatum:
                time = pdatum.split("CPU Time limit:  ")[-1]
                if " second" in time:
                    time = time.split(" second")[0]
            if "Memory limit:  " in pdatum:
                mem = pdatum.split("Memory limit:  ")[-1].rstrip(" MB")

        # Get submission results
        d = []
        r = SESSION.get(URL_SUBMISSION+prob_id)
        soup = BeautifulSoup(r.content, features="html.parser")
        submissions = [t for t in soup.findAll("tr") if t.has_attr("data-submission-id")]
        for submission in submissions:
            sub_time = submission.findChild("td", {"data-type": "time"}).text.strip()
            sub_result = submission.findChild("td", {"data-type": "status"}) \
                                   .findChild("span").get("class")[0]
            prg_time = submission.findChild("td", {"data-type": "cpu"}).text[:-2]
            prg_lang = submission.findChild("td", {"data-type": "lang"}).text

            if len(sub_time) <= 8:
                now = dt.datetime.now()
                sub_time = f"{now.year}-{now.month:02d}-{now.day:02d} {sub_time}"
            if sub_result == "accepted":
                if (d and sub_time < d[0]) or not d:
                    d = [sub_time, prg_time, prg_lang]
        if d:
            d[0] = d[0].split(" ")[0]

        try:
            return (title, prob_id, time, mem, difficulty, *d)
        except:
            # Erroneous file name, hence no Kattis question
            return None

    # Query and write
    with open(PROB_IDS, "w", newline="") as fout:
        for pi in rows:
            result = get(pi)
            if result is not None:
                p = "\t".join(result)
                print(p)
                fout.write(p+"\n")
            else:
                print(pi, "was ignored.")

    ##################################################################3

    # GRAPHINGGGGGGGGGGGGGGGGGGGGGGGGg

    # print("Paste data into repo and close text editor...")
    # os.system(f"notepad {PROB_IDS}")
    #
    # print("Plotting graph...")
    # folder = FOLDER_TOOLS+'\\' if FOLDER_TOOLS else ''
    # os.system(f"python {folder}generate_kattis_graph.py")
    # os.system(f"explorer {folder}progress\\kattis_progress.png")
    # os.system(f"del /f {PROB_IDS}")
    # print("Data recorded and plotted.")


if __name__ == "__main__":
    main()
