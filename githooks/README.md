# Githooks

- hooks run before certain Git actions are executed for my repositories

## adding hooks to your repos with symlinks

- `ln -s /path/to/tools/githooks/pre-push .git/hooks/pre-push`
    - ensures Pylint is run before pushing; blocks push if lint has errors

## apply hooks to all repos in ~/git

- run `apply_pre-push.sh`