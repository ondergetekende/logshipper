from invoke import run, task


@task
def clean(docs=False, bytecode=False, extra=''):
    patterns = ['build']
    if docs:
        patterns.append('docs/_build')
    if bytecode:
        patterns.append('**/*.pyc')
    if extra:
        patterns.append(extra)

    for pattern in patterns:
        run("rm -rf %s" % pattern)


@task
def build_docs():
    import ConfigParser

    config = ConfigParser.ConfigParser()
    config.read(['setup.cfg'])
    with open("docs/outputs.rst", 'w') as f:
        f.write("Outputs\n=======\n\n")
        entry_points = config.get("entry_points", "logshipper.outputs").strip()
        for entry_point in entry_points.splitlines():
            name, path = entry_point.split('=')
            f.write("%(name)s\n"
                    "-------------------------------------------------------\n"
                    "\n"
                    ".. autofunction:: %(path)s\n\n" % {
                        "name": name.strip(),
                        "path": path.strip().replace(":", "."),
                    })

    with open("docs/inputs.rst", 'w') as f:
        f.write("Inputs\n=======\n\n")
        entry_points = config.get("entry_points", "logshipper.inputs").strip()
        for entry_point in entry_points.splitlines():
            name, path = entry_point.split('=')
            f.write("%(name)s\n"
                    "-------------------------------------------------------\n"
                    "\n"
                    ".. autoclass:: %(path)s\n\n" % {
                        "name": name.strip(),
                        "path": path.strip().replace(":", "."),
                    })

    with open("docs/filters.rst", 'w') as f:
        f.write("Filters\n=======\n\n")
        entry_points = config.get("entry_points", "logshipper.filters").strip()
        for entry_point in entry_points.splitlines():
            name, path = entry_point.split('=')
            f.write("%(name)s\n"
                    "-------------------------------------------------------\n"
                    "\n"
                    ".. autofunction:: %(path)s\n\n" % {
                        "name": name.strip(),
                        "path": path.strip().replace(":", "."),
                    })

    run("sphinx-build docs docs/_build")


@task
def build(docs=False):
    run("python setup.py build")
    if docs:
        build_docs()
