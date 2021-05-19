import os
import sys


IGNORE_C_FNS = ["_get_reference_count", "_status", "_free", "_destroy", "_unref", "gdk_device_free_history"]
IGNORE_FNS = [
    "deref", "deref_mut", "drop", "fmt", "clone", "to_value", "g_value_get_flags",
    "g_value_set_flags", "get_type",
]
IGNORE_FNS_START = ["into_glib", "to_glib", "from_glib", "from_raw", "to_raw"]


def is_valid_name(s):
    for c in s:
        if not c.isalnum() and c != '_':
            return False
    for x in IGNORE_C_FNS:
        if s.endswith(x):
            return False
    return True


def get_fn_name(s):
    parts = s.split(" ")
    x = 0
    while x < len(parts) and parts[x] != "fn":
        x += 1
    x += 1
    if x >= len(parts):
        return None
    fn_name = parts[x].split("<")[0].split("(")[0]
    for x in IGNORE_FNS_START:
        if fn_name.startswith(x):
            return None
    if fn_name in IGNORE_FNS:
        return None
    return fn_name


# This to prevent to add the same doc alias more than once on a same function.
def need_doc_alias(content, pos, alias):
    pos -= 1
    while pos >= 0:
        stripped = content[pos].strip()
        if not stripped.startswith("#[") and not stripped.startswith("///"):
            return True
        elif stripped == alias:
            return False
        pos -= 1
    return True


def find_method_in_trait(content, start_line, fn_name):
    if start_line is None:
        # In case the trait hasn't been "discovered" yet or isn't in the same file.
        return None
    start_line += 1
    while start_line < len(content):
        clean = content[start_line].strip()
        if clean.startswith("fn "):
            name = clean[3:].split("<")[0].split("(")[0]
            if name == fn_name:
                return start_line
        elif content[start_line] == "}":
            # We reached the end of the trait declaration and found nothing...
            break
        start_line += 1
    return None


def get_sys_name(line):
    tmp = line.split("ffi::")[1].split("(")[0]
    if tmp == "gtk_init_check":
        tmp = "gtk_init"
    return tmp


def add_parts(path):
    doc_alias_added = 0
    print("=> Updating '{}'".format(path))
    with open(path, 'r') as f:
        content = f.read().split('\n')
    x = 0
    # The key is the trait name, the value is its line number.
    traits = {}
    is_in_trait = None
    while x < len(content):
        clean = content[x].lstrip()
        if not clean.startswith("pub fn") and not clean.startswith("fn"):
            if content[x] == "}":
                is_in_trait = None
            elif (clean.startswith("impl ") or clean.startswith("impl<")) and " for " in clean:
                name = clean.split(" for ")[0].split(" ")[-1].strip()
                if name.endswith("Ext") or name.endswith("ExtManual"):
                    is_in_trait = name
            # This is needed because we want to put Ext traits doc aliases on the trait methods
            # directly and not on their implementation.
            if clean.startswith("pub trait") or clean.startswith("trait"):
                name = clean.split("trait")[1].split("<")[0].split(":")[0].split("{")[0].strip()
                if name.endswith("Ext") or name.endswith("ExtManual"):
                    traits[name] = x
                    # Completely skip the trait declaration.
                    while x < len(content) and content[x] != "}":
                        x += 1
                    continue
            x += 1
            continue

        if clean.endswith(';'): # very likely a trait method declaration.
            x += 1
            continue
        fn_name = get_fn_name(clean)
        if fn_name is None:
            x += 1
            continue
        spaces = ''
        for _ in range(0, len(content[x]) - len(clean)):
            spaces += ' '
        spaces_and_braces = spaces + '}'
        start = x
        need_traits_update = False
        if is_in_trait is not None:
            trait_method_pos = find_method_in_trait(content, traits.get(is_in_trait), fn_name)
            if trait_method_pos is None:
                print("Cannot find `{}` in trait `{}`, putting doc aliases on implementation".format(fn_name, is_in_trait))
            else:
                start = trait_method_pos
                need_traits_update = True
        x += 1
        added = 0
        while x < len(content):
            if content[x] == spaces_and_braces:
                break
            if "ffi::" in content[x]:
                sys_name = get_sys_name(content[x])
                if is_valid_name(sys_name):
                    alias = '#[doc(alias = "{}")]'.format(sys_name)
                    if need_doc_alias(content, start, alias) and fn_name in sys_name:
                        content.insert(start, spaces + alias)
                        doc_alias_added += 1
                        added += 1
                        start += 1
                        x += 1
            x += 1
        if need_traits_update and added > 0:
            # move their start pos
            for trait in traits:
                if traits[trait] > start:
                    traits[trait] += added
        x += 1
    with open(path, 'w') as f:
        f.write('\n'.join(content))
    return doc_alias_added


def run_dirs(path):
    doc_alias_added = 0
    for entry in os.listdir(path):
        full = os.path.join(path, entry)
        if os.path.isdir(full):
            # We don't want to go in auto code parts. They already have everything they need.
            if not entry in ["auto", "subclass"]:
                doc_alias_added += run_dirs(full)
        elif entry.endswith(".rs"):
            doc_alias_added += add_parts(full)
    return doc_alias_added


def main():
    doc_alias_added = 0
    if len(sys.argv) < 2:
        print("No folder given as argument, updating current `src` (if any)")
        doc_alias_added = run_dirs("src")
    else:
        for x in sys.argv[1:]:
            print("> Going into folder `{}`...".format(x))
            doc_alias_added += run_dirs(x)
            print("< Done!")
    print("")
    print("Added {} doc aliases.".format(doc_alias_added))


if __name__ == "__main__":
    main()
