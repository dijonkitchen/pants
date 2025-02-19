---
title: "Custom `python_artifact()` kwargs"
slug: "plugins-setup-py"
excerpt: "How to add your own logic to `python_artifact()`."
hidden: false
createdAt: "2020-09-02T00:21:52.821Z"
---
Pants can build [Python distributions](doc:python-distributions), such as wheels and sdists, from information you provide in a [`python_distribution`](doc:reference-python_distribution) target. 

When doing so, and if you don't provide your own `setup.py` file, Pants generates one and passes it the kwargs provided in the `provides=python_artifact(...)` field to the `setup(...)` call (Pants also generates some of the kwargs, such as `install_requires` and `namespace_packages` by analyzing your code).

It's fairly common to want to generate more of the kwargs dynamically. For example, you may want to:

- Reduce boilerplate by not repeating common kwargs across BUILD files.
- Read from the file system to dynamically determine kwargs, such as the `long_description` or `version`.
- Run processes like `git` to dynamically determine kwargs like `version`.

You can write a plugin to add custom kwarg generation logic.

Note: there may only be at most one applicable plugin per target customizing the kwargs for the `setup()` function.

> 📘 Example
> 
> See [here](https://github.com/pantsbuild/pants/blob/master/pants-plugins/internal_plugins/releases/register.py) for an example that Pants uses internally for its `python_distribution` targets. This plugin demonstrates reading from the file system to set the `version` and `long_description` kwargs, along with adding hardcoded kwargs.

1. Set up a subclass of `SetupKwargsRequest`
--------------------------------------------

Set the class method `is_applicable()` to determine whether your implementation should be used for the particular `python_distribution` target. If `False`, Pants will use the default implementation which simply uses the explicitly provided `python_artifact` from the BUILD file.

In this example, we will always use our custom implementation:

```python
from pants.backend.python.goals.setup_py import SetupKwargsRequest
from pants.engine.target import Target

class CustomSetupKwargsRequest(SetupKwargsRequest):
    @classmethod
    def is_applicable(cls, _: Target) -> bool:
        return True
```

This example will only use our plugin implementation for `python_distribution` targets defined in the folder `src/python/project1`.

```python
class CustomSetupKwargsRequest(SetupKwargsRequest):
    @classmethod
    def is_applicable(cls, target: Target) -> bool:
        return target.address.spec.startswith("src/python/project1")
```

Then, register your new `SetupKwargsRequest ` with a [`UnionRule`](doc:rules-api-unions) so that Pants knows your implementation exists:

```python
from pants.engine.rules import collect_rules
from pants.engine.unions import UnionRule

...

def rules():
    return [
      	*collect_rules(),
        UnionRule(SetupKwargsRequest, CustomSetupKwargsRequest),
    ]
```

> 📘 Consider defining custom `python_distribution` target types
> 
> If you don't want to always use a single custom implementation, an effective approach could be to create custom `python_distribution` target types so that your users decide which implementation they want to use in their BUILD files.
> 
> For example, a user could do this:
> 
> ```python
> pants_python_distribution(
>    name="my-dist",
>    dependencies=[...],
>    provides=python_artifact(...)
> )
> 
> pants_contrib_python_distribution(
>    name="my-dist",
>    dependencies=[...],
>    provides=python_artifact(...)
> )
> ```
> 
> To support this workflow, [create new target types](doc:target-api-new-targets).
> 
> ```python
> class PantsPythonDistribution(Target):
>    alias = "pants_python_distribution"
>    core_fields = PythonDistribution.core_fields
> 
> class PantsContribPythonDistribution(Target):
>    alias = "pants_contrib_python_distribution"
>    core_fields = PythonDistribution.core_fields
> ```
> 
> Then, for each `SetupKwargsRequest` subclass, check which target type was used:
> 
> ```python
> class PantsSetupKwargsRequest(SetupKwargsRequest):
>     @classmethod
>     def is_applicable(cls, target: Target) -> bool:
>         return isinstance(target, PantsPythonDistribution)
> ```

2. Create a rule with your logic
--------------------------------

Your rule should take as a parameter the `SetupKwargsRequest ` from step 1. This type has two fields: `target: Target` and `explicit_kwargs: dict[str, Any]`. You can use these fields to get more information on the target you are generating a `setup.py` for.

Your rule should return `SetupKwargs`, which takes two arguments: `kwargs: dict[str, Any]` and `address: Address`.

For example, this will simply hardcode a kwarg:

```python
from pants.backend.python.goals.setup_py import SetupKwargs
from pants.engine.rules import rule

@rule
async def setup_kwargs_plugin(request: CustomSetupKwargsRequest) -> SetupKwargs:
    return SetupKwargs(
        {**request.explicit_kwargs, "plugin_demo": "hello world"}, address=request.target.address
    )
```

Update your plugin's `register.py` to activate this file's rules.

```python pants-plugins/python_plugins/register.py
from python_plugins import custom_python_artifact

def rules():
   return custom_python_artifact.rules()
```

Then, run `pants package path/to:python_distribution` and inspect the generated `setup.py`to confirm that your plugin worked correctly.

Often, you will want to read from a file in your project to set kwargs like `version` or `long_description`. Use `await Get(DigestContents, PathGlobs)` to do this (see [File system](doc:rules-api-file-system)):

```python
from pants.backend.python.goals.setup_py import SetupKwargs
from pants.engine.fs import DigestContents, GlobMatchErrorBehavior, PathGlobs
from pants.engine.rules import rule

@rule
async def setup_kwargs_plugin(request: CustomSetupKwargsRequest) -> SetupKwargs:
    digest_contents = await Get(
        DigestContents,
        PathGlobs(
            ["project/ABOUT.rst"],
            description_of_origin="`python_artifact()` plugin",
            glob_match_error_behavior=GlobMatchErrorBehavior.error,
        ),
    )
    about_page_content = digest_contents[0].content.decode()
    return SetupKwargs(
        {**request.explicit_kwargs, "long_description": "\n".join(about_page_content)},
        address=request.target.address
    )
```

It can be helpful to allow users to add additional kwargs to their BUILD files for you to consume in your plugin. For example, this plugin adds a custom `long_description_path` field, which gets popped and replaced by the plugin with a normalized `long_description` kwarg:

```python
python_distribution(
    name="mydist",
    dependencies=[...],
    provides=python_artifact(
        name="mydist",
        ...
        long_description_path="README.md",
    ),
    generate_setup = True,
    sdist = False,
)
```

```python
import os.path

from pants.backend.python.goals.setup_py import SetupKwargs
from pants.engine.fs import DigestContents, GlobMatchErrorBehavior, PathGlobs
from pants.engine.rules import rule

@rule
async def setup_kwargs_plugin(request: CustomSetupKwargsRequest) -> SetupKwargs:
    original_kwargs = request.explicit_kwargs.copy()
    long_description_relpath = original_kwargs.pop("long_description_file", None)
    if not long_description_relpath:
        raise ValueError(
            f"The python_distribution target {request.target.address} did not include "
            "`long_description_file` in its python_artifact's kwargs. Our plugin requires this! "
            "Please set to a path relative to the BUILD file, e.g. `ABOUT.md`."
        )

    build_file_path = request.target.address.spec_path
    long_description_path = os.path.join(build_file_path, long_description_relpath)
    digest_contents = await Get(
        DigestContents,
        PathGlobs(
            [long_description_path],
            description_of_origin=f"the 'long_description_file' kwarg in {request.target.address}",
            glob_match_error_behavior=GlobMatchErrorBehavior.error,
        ),
    )
    description_content = digest_contents[0].content.decode()
    return SetupKwargs(
        {**original_kwargs, "long_description": "\n".join(description_content)},
        address=request.target.address
    )
```

Refer to these guides for additional things you may want to do in your plugin:

- [Read from options](doc:rules-api-subsystems). Also see [here](https://github.com/pantsbuild/pants/blob/master/pants-plugins/internal_plugins/releases/register.py) for an example.
- [Read values from the target](doc:rules-api-and-target-api) using the Target API.
- [Run a `Process`](doc:rules-api-process), such as `git`. Also see [Installing tools](doc:rules-api-installing-tools).
