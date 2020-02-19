# checker

Repository which contains various scripts to run for CI.

## Check missing manual traits in Gir.toml

If you run through `Cargo`, it'll check if some manual traits aren't missing from the `Gir.toml` file:

```bash
$ cargo run -- [gtk-rs project folder]
```

You can pass multiple folders as argument.

## Check missing init asserts

Some functions have to be called before some others in GTK. This script ensures it has this check in those functions. You can run it as follows:

```bash
$ ./check_init_asserts
```
