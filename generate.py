#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
Options:

 -c Clear local repos and clone everything again
 -o Offline, don't clone or pull remote repos

TODO:
- read scripts/ dir and run the preparation scripts
- 

'''

from ConfigParser import SafeConfigParser
import jinja2
import git, os, shutil
import logging
import markdown
import json
import codecs
from pprint import pprint

config_file = "datasets.conf"
output_dir = "_output"
template_dir = "templates"
repo_dir = "repos"

logging.basicConfig(level=logging.DEBUG)
env = jinja2.Environment(loader=jinja2.FileSystemLoader([template_dir]))

def create_index_page(packages):
    '''Generates the index page with the list of available packages.
    Accepts a list of pkg_info dicts, which are generated with the
    process_datapackage function.'''
    template = env.get_template("list.html")
    target = "index.html"
    datapackages = [p['name'] for p in packages]
    contents = template.render(datapackages=datapackages)

    f = codecs.open(os.path.join(output_dir, target), 'w', 'utf-8')
    f.write(contents)
    f.close()
    logging.info("Created index.html.")

def create_dataset_page(pkg_info):
    '''Generate a single dataset page.'''
    template = env.get_template("dataset.html")
    name = pkg_info["name"]
    target = os.path.join("datasets/", name+".html")

    context = {"title": pkg_info["title"],
               "description": pkg_info["description"],
               "readme": pkg_info["readme"],
               "datafiles": pkg_info["datafiles"],
              }
    contents = template.render(**context)

    f = codecs.open(os.path.join(output_dir, target), 'w', 'utf-8')
    f.write(contents)
    f.close()
    logging.info("Created %s." % target)


def process_datapackage(pkg_name):
    '''Reads a data package and returns a dict with its metadata. The items in
    the dict are:
        - name
        - title
        - license
        - description
        - readme (in HTML, processed with python-markdown from README.md, empty if README.md
          does not exist)
        - datafiles (a dict that contains the contents of the "resources" attribute)
    '''
    pkg_dir = os.path.join(repo_dir, pkg_name)
    pkg_info = {}
    metadata = json.loads(open(os.path.join(pkg_dir, "datapackage.json")).read())

    # get main attributes
    pkg_info['name'] = pkg_name
    pkg_info['title'] = metadata['title']
    pkg_info['license'] = metadata['licenses'][0]
    pkg_info['description'] = metadata['description']
    # process README
    readme = ""
    readme_path = os.path.join(pkg_dir, "README.md")
    if not os.path.exists(readme_path):
        logging.warn("No README.md file found in the data package.")
    else:
        logging.info("README.md file found.")
        contents = open(readme_path, 'r').read()
        readme = markdown.markdown(contents, output_format="html5", encoding="UTF-8")
    pkg_info['readme'] = readme
    # process resource/datafiles list
    for r in metadata['resources']:
        r['basename'] = os.path.basename(r['path'])
    pkg_info['datafiles'] = metadata['resources']

    return pkg_info    

def generate():
    '''Main function that takes care of the whole process.'''
    # set up the output directory
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.mkdir(output_dir)
    # set up the dir for storing repositories
    if not os.path.exists(repo_dir):
        logging.info("Directory %s doesn't exist, creating it." % repo_dir)
        os.mkdir(repo_dir)
    # create dir for dataset pages
    os.mkdir(os.path.join(output_dir, "datasets"))
    # create dir for storing data files for download
    os.mkdir(os.path.join(output_dir, "files"))
    # create static dirs
    shutil.copytree("static/css", os.path.join(output_dir, "css"))
    shutil.copytree("static/js", os.path.join(output_dir, "js"))
    shutil.copytree("static/img", os.path.join(output_dir, "img"))
    shutil.copytree("static/fonts", os.path.join(output_dir, "fonts"))

    # read the config file to get the datasets we want to publish
    parser = SafeConfigParser()
    parser.read(config_file)
    packages = []
    # go through each specified dataset
    for s in parser.sections():
        dir_name = os.path.join(repo_dir, s)
        remote_url = parser.get(s, 'url')
        # clone/pull Git repository
        if os.path.isdir(dir_name):
            logging.info("Repo '%s' already exists, pulling changes..." % s)
            repo = git.Repo(dir_name)
            origin = repo.remotes.origin
            origin.fetch()
            result = origin.pull()[0]
            if result.flags & result.HEAD_UPTODATE:
                logging.info("Repo '%s' is up to date." % s)
            else:
                # TODO: figure out the other git-python flags and return more
                # informative logging output
                logging.info("Repo changed, updating. (returned flags: %d)" % result.flags)
        else:
            logging.info("We don't have repo '%s', cloning..." % s)
            repo = git.Repo.clone_from(remote_url, dir_name)
         
        # get datapackage metadata
        pkg_info = process_datapackage(s)
        # add it to the packages list for index page generation after the loop ends
        packages.append(pkg_info)
        # generate the dataset HTML page
        create_dataset_page(pkg_info)
        # copy the datafiles to the files/ dir for download
        datafiles = pkg_info['datafiles']
        for d in datafiles:
            logging.info("Copying %s to the %s/files dir." % (d['basename'], output_dir))
            target = os.path.join(output_dir, 'files/', os.path.basename(d['path']))
            shutil.copyfile(os.path.join(dir_name, d['path']), target)
    # generate the HTML index with the list of available packages
    create_index_page(packages)

if __name__ == "__main__":
    generate()


