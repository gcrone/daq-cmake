#!/usr/bin/env python3

import argparse
import os
import pathlib
import re
import shutil
import string
import subprocess
import sys
import tempfile

if "DBT_ROOT" in os.environ:
    sys.path.append(f'{os.environ["DBT_ROOT"]}/scripts')
else:
    print("ERROR: daq-buildtools environment needs to be set up for this script to work. Exiting...")
    sys.exit(1)

from dbt_setup_tools import error, get_time

usage_blurb=f"""

Usage
-----

This script creates the boilerplate of a new DUNE DAQ package. In
general, the more you know about your package in advance (e.g. whether
it should contain DAQModules and what their names should be, etc.) the
more work this script can do for you.

Simplest usage:
{os.path.basename (__file__)} <name of new repo in DUNE-DAQ>\n\n")

...where the new repo must be empty with the exception of an optional README.md. 

Arguments and options:

--main-library: package will contain a main, package-wide library which other packages can link in

--python-bindings: whether there will be python bindings to components in a main library

--daq-module: for each "--daq-module <module name>" provided at the commandline, the framework for a DAQModule will be auto-generated

--user-app: same as --daq-module, but for user applications

--test-app: same as --daq-module, but for integration test applications

"""

parser = argparse.ArgumentParser(usage=usage_blurb)
parser.add_argument("--main-library", action="store_true", dest="contains_main_library", help=argparse.SUPPRESS)
parser.add_argument("--python-bindings", action="store_true", dest="contains_python_bindings", help=argparse.SUPPRESS)
parser.add_argument("--daq-module", action="append", dest="daq_modules", help=argparse.SUPPRESS)
parser.add_argument("--user-app", action="append", dest="user_apps", help=argparse.SUPPRESS)
parser.add_argument("--test-app", action="append", dest="test_apps", help=argparse.SUPPRESS)
parser.add_argument("package", nargs="?", help=argparse.SUPPRESS)

args = parser.parse_args()

if args.package is not None: 
    package = args.package
else:
    print(usage_blurb)
    sys.exit(1)

#package_repo = f"https://github.com/DUNE-DAQ/{package}/"
package_repo = f"https://github.com/jcfreeman2/{package}/"  # jcfreeman2 is for testing purposes since there's no guaranteed-empty-repo in DUNE-DAQ

this_scripts_directory=pathlib.Path(__file__).parent.resolve()
templatedir = f"{this_scripts_directory}/templates"

if "DBT_AREA_ROOT" in os.environ:
    sourcedir = os.environ["DBT_AREA_ROOT"] + "/sourcecode"
else:
    error("""
The environment variable DBT_AREA_ROOT doesn't appear to be defined. 
You need to have a work area environment set up for this script to work. Exiting...
""")


repodir = f"{sourcedir}/{package}"
os.chdir(f"{sourcedir}")

proc = subprocess.Popen(f"git clone {package_repo}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
proc.communicate()
retval = proc.returncode

if retval == 128:
    error(f"""
git was either unable to find a {package_repo} repository or it already existed 
in {os.getcwd()} and couldn't be overwritten
    """)
elif retval != 0:
    error(f"Totally unexpected error (return value {retval}) occurred when running \"git clone {package_repo}\"")

def cleanup(repodir):
    if os.path.exists(repodir):

        # This code is very cautious so that it rm -rf's the directory it expects 
        if re.search(f"/{package}", repodir):
            shutil.rmtree(repodir)
        else:
            assert False, f"DEVELOPER ERROR: This script does not trust that the directory \"{repodir}\" is something it should delete since it doesn't look like a local repo for {package}"
    else:
        assert False, f"DEVELOPER ERROR: This script is unable to locate the expected repo directory {repodir}"

def make_package_dir(dirname):
    os.makedirs(dirname, exist_ok=True)
    if not os.path.exists(f"{dirname}/.gitkeep"):
        open(f"{dirname}/.gitkeep", "w")

os.chdir(repodir)

if os.listdir(repodir) != [".git"] and sorted(os.listdir(repodir)) != [".git", "README.md"] and sorted(os.listdir(repodir)) != [".git", "docs"]:
    cleanup(repodir)
    error(f"""

Just ran \"git clone {package_repo}\", and it looks like this repo isn't empty. 
This script can only be run on repositories which haven't yet been worked on.
""")

find_package_calls = []
daq_codegen_calls = []
daq_add_library_calls = []
daq_add_python_bindings_calls = []
daq_add_plugin_calls = []
daq_add_application_calls = []
daq_add_unit_test_calls = []

print("")

if args.contains_main_library:
    make_package_dir(f"{repodir}/src")
    make_package_dir(f"{repodir}/include")
    daq_add_library_calls.append("daq_add_library( LINK_LIBRARIES ) # Any source files and/or dependent libraries to link in not yet determined")

if args.contains_python_bindings:
    make_package_dir(f"{repodir}/pybindsrc")
    daq_add_python_bindings_calls.append("\ndaq_add_python_bindings(*.cpp LINK_LIBRARIES ${PROJECT_NAME} ) # Any additional libraries to link in beyond the main library not yet determined\n")

    for src_filename in ["module.cpp", "renameme.cpp"]:
        shutil.copyfile(f"{templatedir}/{src_filename}", f"{repodir}/pybindsrc/{src_filename}")

if args.daq_modules:

    for filename in ["RenameMe.hpp", "RenameMe.cpp"]:
        assert os.path.exists(f"{templatedir}/{filename}")

    for pkg in ["appfwk", "opmonlib"]:
        find_package_calls.append(f"find_package({pkg} REQUIRED)")

    make_package_dir(f"{repodir}/src")
    make_package_dir(f"{repodir}/plugins")
    make_package_dir(f"{repodir}/schema/{package}")

    for module in args.daq_modules:
        if not re.search(r"^[A-Z][^_]+", module):
            cleanup(repodir)
            error(f"""
Requested module name \"{module}\" needs to be in PascalCase. 
Please see https://dune-daq-sw.readthedocs.io/en/latest/packages/styleguide/ for more on naming conventions.
Exiting...
""")

        daq_add_plugin_calls.append(f"daq_add_plugin({module} duneDAQModule LINK_LIBRARIES appfwk::appfwk) # Replace appfwk library with a more specific library when appropriate")
        daq_codegen_calls.append(f"daq_codegen({module.lower()}.jsonnet TEMPLATES Structs.hpp.j2 Nljs.hpp.j2)") 
        daq_codegen_calls.append(f"daq_codegen({module.lower()}info.jsonnet DEP_PKGS opmonlib TEMPLATES opmonlib/InfoStructs.hpp.j2 opmonlib/InfoNljs.hpp.j2)")

        for src_filename in ["RenameMe.hpp", "RenameMe.cpp", "renameme.jsonnet", "renamemeinfo.jsonnet"]:

            if pathlib.Path(src_filename).suffix in [".hpp", ".cpp"]:
                dest_filename = src_filename.replace("RenameMe", module)
                dest_filename = f"{repodir}/plugins/{dest_filename}"
            elif pathlib.Path(src_filename).suffix in [".jsonnet"]:
                dest_filename = src_filename.replace("renameme", module.lower())
                dest_filename = f"{repodir}/schema/{package}/{dest_filename}"
            else:
                assert False, "DEVELOPER ERROR: unhandled filename"

            shutil.copyfile(f"{templatedir}/{src_filename}", dest_filename)

            with open(f"{templatedir}/{src_filename}", "r") as inf:
                sourcecode = inf.read()
                    
            sourcecode = sourcecode.replace("RenameMe", module)

            # Handle the header guards
            sourcecode = sourcecode.replace("PACKAGE", package.upper())
            sourcecode = sourcecode.replace("RENAMEME", module.upper())

            # Handle namespace
            sourcecode = sourcecode.replace("package", package.lower())

            # And schema files
            sourcecode = sourcecode.replace("renameme", module.lower())

            with open(dest_filename, "w") as outf:
                outf.write(sourcecode)

if args.user_apps:
    make_package_dir(f"{repodir}/apps")

    for user_app in args.user_apps:
        if re.search(r"[A-Z]", user_app):
            cleanup(repodir)
            error(f"""
Requested user application name \"{user_app}\" needs to be in snake_case. 
Please see https://dune-daq-sw.readthedocs.io/en/latest/packages/styleguide/ for more on naming conventions.
Exiting...
""")
        dest_filename = f"{repodir}/apps/{user_app}.cxx"
        with open(f"{templatedir}/renameme.cxx") as inf:
            sourcecode = inf.read()

        sourcecode = sourcecode.replace("renameme", user_app)

        with open(dest_filename, "w") as outf:
            outf.write(sourcecode)

        daq_add_application_calls.append(f"daq_add_application({user_app} {user_app}.cxx LINK_LIBRARIES ) # Any libraries to link in not yet determined")
    

if args.test_apps:
    make_package_dir(f"{repodir}/test/apps")

    for test_app in args.test_apps:
        if re.search(r"[A-Z]", test_app):
            cleanup(repodir)
            error(f"""
Requested test application name \"{test_app}\" needs to be in snake_case. 
Please see https://dune-daq-sw.readthedocs.io/en/latest/packages/styleguide/ for more on naming conventions.
Exiting...
""")
        dest_filename = f"{repodir}/test/apps/{test_app}.cxx"
        with open(f"{templatedir}/renameme.cxx") as inf:
            sourcecode = inf.read()
    
        sourcecode = sourcecode.replace("renameme", test_app)

        with open(dest_filename, "w") as outf:
            outf.write(sourcecode)

        daq_add_application_calls.append(f"daq_add_application({test_app} {test_app}.cxx TEST LINK_LIBRARIES ) # Any libraries to link in not yet determined")

make_package_dir(f"{repodir}/unittest")
shutil.copyfile(f"{templatedir}/Placeholder_test.cxx", f"{repodir}/unittest/Placeholder_test.cxx")
daq_add_unit_test_calls.append("daq_add_unit_test(Placeholder_test LINK_LIBRARIES)  # Any libraries to link in not yet determined")
find_package_calls.append("find_package(Boost COMPONENTS unit_test_framework REQUIRED)")

make_package_dir(f"{repodir}/docs")
if not os.path.exists(f"{repodir}/README.md"):
    with open(f"{repodir}/docs/README.md", "w") as outf:
        generation_time = get_time("as_date")
        outf.write(f"# No Official User Documentation Has Been Written Yet ({generation_time})\n")
else:
    os.chdir(repodir)
    proc = subprocess.Popen(f"pwd; git mv README.md docs/README.md", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    proc.communicate()
    retval = proc.returncode
    if retval != 0:
        cleanup(repodir)
        error(f"There was a problem attempting a git mv of README.md to docs/README.md in {repodir}; exiting...")

make_package_dir(f"{repodir}/cmake")
config_template_html=f"https://raw.githubusercontent.com/DUNE-DAQ/daq-cmake/dunedaq-v2.6.0/configs/Config.cmake.in"
proc = subprocess.Popen(f"curl -o {repodir}/cmake/{package}Config.cmake.in -O {config_template_html}", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
proc.communicate()
retval = proc.returncode

if retval != 0:
    cleanup(repodir)
    error(f"There was a problem trying to pull down {config_template_html} from the web; exiting...")

def print_cmakelists_section(list_of_calls, section_of_webpage = None):
    for i, line in enumerate(list_of_calls):
        if i == 0 and section_of_webpage is not None:
            cmakelists.write(f"\n# See https://dune-daq-sw.readthedocs.io/en/latest/packages/daq-cmake/#{section_of_webpage}\n") 
        cmakelists.write("\n" + line)

    if len(list_of_calls) > 0:
        cmakelists.write("""

##############################################################################

""")

with open("CMakeLists.txt", "w") as cmakelists:
    generation_time = get_time("as_date")
    cmakelists.write(f"""

# This is a skeleton CMakeLists.txt file, auto-generated on {generation_time}. 
# The developer(s) of this package should delete this comment as well
# as adding dependent targets, packages, etc.  which the
# auto-generator can't know about. For details on how to write a
# package, please see
# https://dune-daq-sw.readthedocs.io/en/latest/packages/daq-cmake/

cmake_minimum_required(VERSION 3.12)
project({package} VERSION 0.0.0)

find_package(daq-cmake REQUIRED)

daq_setup_environment()

""")

    print_cmakelists_section(find_package_calls)
    print_cmakelists_section(daq_codegen_calls, "daq_codegen")
    print_cmakelists_section(daq_add_library_calls, "daq_add_library")
    print_cmakelists_section(daq_add_python_bindings_calls, "daq_add_python_bindings")
    print_cmakelists_section(daq_add_plugin_calls, "daq_add_plugin")
    print_cmakelists_section(daq_add_application_calls, "daq_add_application")
    print_cmakelists_section(daq_add_unit_test_calls, "daq_add_unit_test")

    cmakelists.write("daq_install()\n\n")

os.chdir(repodir)

# Only need .gitkeep if the directory is otherwise empty
for filename, ignored, ignored in os.walk(repodir):
    if os.path.isdir(filename) and os.listdir(filename) != [".gitkeep"]:
        if os.path.exists(f"{filename}/.gitkeep"):
            os.unlink(f"{filename}/.gitkeep")

proc = subprocess.Popen("git add -A", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
proc.communicate()
retval = proc.returncode

if retval != 0:
    error(f"""
There was a problem trying to "git add" the newly-created files and directories in {repodir}; exiting...
""")

command=" ".join(sys.argv)
proc = subprocess.Popen(f"git commit -m \"This {os.path.basename (__file__)}-generated boilerplate for the {package} package was created by this command: {command}\"", shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
proc.communicate()
retval = proc.returncode

if retval != 0:
    error(f"""
There was a problem trying to auto-generate the commit off the newly auto-generated files in {repodir}. Exiting...
""")

