use crate::types::CheckResult;

use std::collections::HashSet;
use std::fs;
use std::path::Path;

use toml::Value;

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

#[derive(Debug)]
struct Info {
    correctly_declared_manual_traits: HashSet<String>,
    listed_crate_objects: HashSet<String>,
}

// Return a map where the key is the full object name and has the manual associated traits.
fn get_objects(toml_file: &Path) -> CheckResult<Info> {
    println!("==> Getting objects from {:?}", toml_file.display());
    let mut correctly_declared_manual_traits: HashSet<String> = HashSet::new();
    let mut listed_crate_objects: HashSet<String> = HashSet::new();

    let toml: Value = toml::from_str(
        &fs::read_to_string(toml_file)
            .map_err(|e| format!("Failed to read {:?}: {}", toml_file, e))?,
    )
    .expect("invalid toml");

    let current_lib = toml
        .lookup_str("options.library")
        .expect("failed to get current library");
    for entry in get_vec!(toml, "options.generate")
        .iter()
        .filter_map(|x| x.as_str())
    {
        listed_crate_objects.insert(
            entry
                .split('.')
                .nth(1)
                .expect("couldn't extract name")
                .to_owned(),
        );
    }
    for entry in get_vec!(toml, "options.builders")
        .iter()
        .filter_map(|x| x.as_str())
    {
        listed_crate_objects.insert(
            entry
                .split('.')
                .nth(1)
                .expect("couldn't extract name")
                .to_owned(),
        );
    }
    for entry in get_vec!(toml, "options.manual")
        .iter()
        .filter_map(|x| x.as_str())
    {
        let mut parts = entry.split('.');
        let lib = parts.next().expect("failed to extract lib");
        if lib != current_lib {
            continue;
        }
        listed_crate_objects.insert(parts.next().expect("couldn't extract name").to_owned());
    }
    if let Some(objs) = toml.lookup("object").map(|a| a.as_array().unwrap()) {
        for obj in objs {
            if let Some(name) = obj.lookup_str("name") {
                let mut parts = name.split('.');
                let lib = parts.next().expect("failed to extract lib");
                if lib != current_lib {
                    continue;
                }
                if let Some(name) = parts.next() {
                    for elem in get_vec!(obj, "manual_traits")
                        .iter()
                        .filter_map(|x| x.as_str())
                        .map(|x| x.to_owned())
                    {
                        correctly_declared_manual_traits.insert(elem);
                    }
                    listed_crate_objects.insert(name.to_owned());
                }
            }
        }
    }
    println!("<== done");
    Ok(Info {
        correctly_declared_manual_traits,
        listed_crate_objects,
    })
}

fn get_manual_traits_from_file(
    src_file: &Path,
    objects: &Info,
    ret: &mut Vec<String>,
) -> CheckResult<()> {
    let content = fs::read_to_string(src_file)
        .map_err(|e| format!("Failed to read {:?}: {}", src_file, e))?;
    for line in content.lines() {
        let line = line.trim();
        if !line.starts_with("pub trait ") {
            continue;
        }
        let line = &line[10..];
        let mut pos = (line.find('{').unwrap_or_else(|| line.len()), '{');
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
        let obj = &name[..name.len() - 9];
        if !objects.correctly_declared_manual_traits.contains(name)
            && objects.listed_crate_objects.contains(obj)
        {
            ret.push(name.to_owned());
        }
    }

    Ok(())
}

fn get_manual_traits(src_dir: &Path, objects: &Info) -> CheckResult<Vec<String>> {
    println!("==> Getting manual traits from {:?}", src_dir.display());
    let mut ret = Vec::new();

    for entry in fs::read_dir(src_dir)
        .map_err(|e| format!("Failed to read directory {:?}: {}", src_dir, e))?
    {
        let entry = entry.expect("Failed to enter directory");
        let path = entry.path();
        if !path.is_dir() {
            get_manual_traits_from_file(&path, objects, &mut ret)?;
        }
    }
    println!("<== done");
    Ok(ret)
}

pub fn run_check<P: AsRef<Path>>(folder: &P, gir_file: &str) -> CheckResult<bool> {
    let folder = folder.as_ref();
    let objects = get_objects(&folder.join(gir_file))?;
    let results = get_manual_traits(&folder.join("src"), &objects)?;
    if !results.is_empty() {
        println!("xx> Some manual traits are missing from the Gir.toml file:");
        for result in results.iter() {
            println!("{}", result);
        }
    }
    Ok(results.is_empty())
}
