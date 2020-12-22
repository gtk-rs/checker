use std::fs;
use std::io::{BufRead, BufReader};
use std::path::Path;

use crate::types::CheckResult;

fn check_if_valid_indent(path: &Path) -> CheckResult<bool> {
    if !path.extension().map(|ex| ex == "toml").unwrap_or(false) {
        return Ok(true);
    }
    let f =
        fs::File::open(path).map_err(|e| format!("Failed to open `{}`: {}", path.display(), e))?;
    let f = BufReader::new(f);
    for (nb_line, line) in f.lines().enumerate() {
        let line = line.unwrap();
        if (line.len() - line.trim_start().len()) % 4 != 0 {
            println!(
                "xx> Invalid indent in `{}:{}`: it must be a multiple of 4!",
                path.display(),
                nb_line + 1
            );
            return Ok(false);
        }
    }
    Ok(true)
}

fn inner_indent_check(folder: &Path) -> CheckResult<usize> {
    let mut nb_errors = 0;
    for entry in fs::read_dir(folder)
        .map_err(|e| format!("Failed to read directory `{}`: {}", folder.display(), e))?
    {
        let entry = entry.expect("Failed to enter directory");
        let path = entry.path();
        if !path.is_dir() {
            if !check_if_valid_indent(&path)? {
                nb_errors += 1;
            }
        } else {
            nb_errors += inner_indent_check(&path)?;
        }
    }
    Ok(nb_errors)
}

pub fn run_check<P: AsRef<Path>>(folder: &P) -> CheckResult<bool> {
    let folder = folder.as_ref();
    println!("==> Checking gir files indent in `{}`", folder.display());
    let nb_errors = inner_indent_check(folder)?;
    println!("<== done");
    Ok(nb_errors == 0)
}
