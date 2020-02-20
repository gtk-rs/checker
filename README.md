# checker

Repository which contains various scripts to run for CI.

## Check missing manual traits in Gir.toml

If you run through `Cargo`, it'll check if some manual traits aren't missing
from the `Gir.toml` file:

```bash
$ cargo run -- [project folder]
```

You can set the gir file using the `--gir-file` flag. Note that it'll be used
for all the next folders and it's relative as well! For example:

```bash
$ cargo run -- [project folder1] --gir-file [some_file] [project folder 2] [project folder 3]
```

`[some file]` will be used for `[project folder 2]` AND `[project folder 3]`.
Also, like said previously, the gir file argument is a relative path from the
project folder.

You can pass multiple folders as argument.

## Check missing init asserts

Some functions have to be called before some others in GTK. This script ensures it has this check in those functions. You can run it as follows:

```bash
$ ./check_init_asserts
```
