extern crate toml;

use std::collections::HashSet;
use std::env;
use std::fs;
use std::path::Path;
use std::process::exit;

use toml::Value;

macro_rules! get_vec {
    ($toml:expr, $key:expr) => {{
        match $toml.lookup_vec($key) {
            Some(v) => v.as_slice(),
            None => &[],
        }
    }};
}

// This trait comes from https://github.com/gtk-rs/gir
pub trait TomlHelper
where
    Self: Sized,
{
    fn lookup<'a>(&'a self, option: &str) -> Option<&'a toml::Value>;
    fn lookup_str<'a>(&'a self, option: &'a str) -> Option<&'a str>;
    fn lookup_vec<'a>(&'a self, option: &'a str) -> Option<&'a Vec<Self>>;
}

impl TomlHelper for toml::Value {
    fn lookup<'a>(&'a self, option: &str) -> Option<&'a toml::Value> {
        let mut value = self;
        for opt in option.split('.') {
            let table = match value.as_table() {
                Some(table) => table,
                None => return None,
            };
            value = match table.get(opt) {
                Some(value) => value,
                None => return None,
            };
        }
        Some(value)
    }
    fn lookup_str<'a>(&'a self, option: &'a str) -> Option<&'a str> {
        self.lookup(option)?.as_str()
    }
    fn lookup_vec<'a>(&'a self, option: &'a str) -> Option<&'a Vec<Self>> {
        self.lookup(option)?.as_array()
    }
}

// Return a map where the key is the full object name and has the manual associated traits.
fn get_objects(toml_file: &Path) -> HashSet<String> {
    let toml: Value = toml::from_str(&fs::read_to_string(toml_file).expect("failed to read toml"))
        .expect("invalid toml");
    let mut map: HashSet<String> = HashSet::new();

    for objs in toml.lookup("object").map(|a| a.as_array().unwrap()) {
        for obj in objs {
            if let Some(_) = obj.lookup_str("name") {
                for elem in get_vec!(obj, "manual_traits")
                    .iter()
                    .filter_map(|x| x.as_str())
                    .map(|x| x.to_owned())
                {
                    map.insert(elem);
                }
            }
        }
    }
    map
}

fn get_manual_traits_from_file(src_file: &Path, objects: &HashSet<String>, ret: &mut Vec<String>) {
    let content = fs::read_to_string(src_file).expect("failed to read source file");
    for line in content.lines() {
        let line = line.trim();
        if !line.starts_with("pub trait ") {
            continue;
        }
        let line = &line[10..];
        let mut pos = (line.find('{').unwrap_or(line.len()), '{');
        for x in &['<', ':'] {
            if let Some(p) = line.find(*x) {
                if p < pos.0 {
                    pos.0 = p;
                    pos.1 = *x;
                }
            }
        }
        let name = line.split(pos.1).next().expect("failed to get trait name");
        if !name.ends_with("ExtManual") {
            continue;
        }
        if !objects.contains(name) {
            ret.push(name.to_owned());
        }
    }
}

fn get_manual_traits(src_dir: &Path, objects: &HashSet<String>) -> Vec<String> {
    let mut ret = Vec::new();

    for entry in fs::read_dir(src_dir).expect("read_dir failed") {
        let entry = entry.expect("failed to read entry");
        let path = entry.path();
        if !path.is_dir() {
            get_manual_traits_from_file(&path, objects, &mut ret);
        }
    }
    ret
}

fn run_check<P: AsRef<Path>>(folder: P) -> bool {
    let folder = folder.as_ref();
    println!("=> Running for {}", folder.display());

    let objects = get_objects(&folder.join("Gir.toml"));
    let results = get_manual_traits(&folder.join("src"), &objects);
    if !results.is_empty() {
        println!("==> Some manual traits are missing from the Gir.toml file:");
        for result in results.iter() {
            println!("{}", result);
        }
    }
    println!("<= done");
    results.is_empty()
}

fn main() {
    let mut result = true;
    for arg in env::args().into_iter().skip(1) {
        if !run_check(&arg) {
            result = false;
        }
    }
    if !result {
        eprintln!("failed");
        exit(1);
    }
    println!("success!");
}
