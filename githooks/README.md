# Githooks

Hooks run before certain Git actions for repositories under `~/git`.

## adding hooks to a single repo

```sh
ln -s /path/to/tools/githooks/pre-commit .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

The pre-commit hook runs Pylint on staged Python files and blocks the commit if lint has errors.

## apply hooks to all repos in ~/git

```sh
/path/to/tools/githooks/apply_hooks.sh
```

This symlinks `pre-commit` into every repo under `~/git` and removes legacy `pre-push` hooks that pointed at the old script.

On a new machine, hooks are installed automatically when the dotfiles playbook runs with the `git` tag, as long as `~/git/tools` is already cloned.
