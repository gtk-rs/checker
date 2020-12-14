extern crate toml;

use std::env;
use std::path::Path;
use std::process::exit;

macro_rules! get_vec {
    ($toml:expr, $key:expr) => {{
        match $toml.lookup_vec($key) {
            Some(v) => v.as_slice(),
            None => &[],
        }
    }};
}

mod license;
mod manual_traits;
mod types;

fn run_check<P: AsRef<Path>>(folder: P, gir_file: &str) -> types::CheckResult<bool> {
    println!("=> Running for {}", folder.as_ref().display());
    let result = manual_traits::run_check(&folder, gir_file)? && license::run_check(&folder)?;
    println!("<= done");
    Ok(result)
}

fn show_help() {
    println!("== checker options ==");
    println!("  --gir-file   : Set gir file path to be used for all following folders");
    println!("  -h | --help  : Display this help");
    println!("");
    println!("Any other argument will be the folder to run `checker` into.");
}

fn main() -> types::CheckResult<()> {
    let mut gir_file = "Gir.toml".to_owned();
    let mut result = true;
    let args = env::args().into_iter().skip(1).collect::<Vec<_>>();
    let mut i = 0;
    while i < args.len() {
        let arg = &args[i];
        if arg == "--gir-file" {
            i += 1;
            if i >= args.len() {
                break;
            }
            gir_file = args[i].to_owned();
        } else if arg == "--help" || arg == "-h" {
            show_help();
            return Ok(());
        } else {
            if !run_check(&arg, &gir_file)? {
                result = false;
            }
        }
        i += 1;
    }
    if !result {
        eprintln!("failed");
        exit(1);
    }
    println!("success!");
    Ok(())
}
