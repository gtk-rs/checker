use std::fs;
use std::io::{BufRead, BufReader};
use std::path::Path;

use crate::types::CheckResult;

fn check_if_license_is_present(path: &Path) -> CheckResult<bool> {
    let f =
        fs::File::open(path).map_err(|e| format!("Failed to open `{}`: {}", path.display(), e))?;
    let f = BufReader::new(f);
    let header: Vec<String> = f.lines().take(2).map(|x| x.unwrap()).collect();
    if header.len() != 2 {
        println!("xx> Missing header in `{}`", path.display());
        Ok(false)
    } else if header[0]
        != "// Take a look at the license at the top of the repository in the LICENSE file."
    {
        println!("xx> Missing header in `{}`", path.display());
        Ok(false)
    } else if !header[1].is_empty() {
        println!(
            "xx> Expected empty line after license header in `{}`",
            path.display()
        );
        Ok(false)
    } else {
        Ok(true)
    }
}

pub fn run_check<P: AsRef<Path>>(folder: &P) -> CheckResult<bool> {
    let folder = folder.as_ref();
    let src_dir = folder.join("src");
    println!("==> Checking license headers from {:?}", src_dir.display());
    let mut nb_errors = 0;
    for entry in fs::read_dir(&src_dir)
        .map_err(|e| format!("Failed to read directory {:?}: {}", src_dir, e))?
    {
        let entry = entry.expect("Failed to enter directory");
        let path = entry.path();
        if !path.is_dir() {
            if !check_if_license_is_present(&path)? {
                nb_errors += 1;
            }
        }
    }
    println!("<== done");
    Ok(nb_errors == 0)
}
