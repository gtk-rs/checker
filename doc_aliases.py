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
        if not stripped.startswith("#[") and not stripped.startswith("//"):
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


def find_variant_in_enum(content, start_line, variant_name):
    if start_line is None:
        # In case the enum hasn't been "discovered" yet or isn't in the same file.
        return None
    start_line += 1
    while start_line < len(content):
        clean = content[start_line].strip()
        if clean.endswith(",") and not clean.startswith("//") and not clean.startswith("#["):
            name = clean[:-1].split("(")[0].strip()
            if name == variant_name:
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


def generate_start_spaces(line, clean):
    spaces = ''
    for _ in range(0, len(line) - len(clean)):
        spaces += ' '
    return spaces


def add_variant_doc_alias(content, clean, enums, is_in_enum):
    parts = clean.split(" => ")
    ffi_variant = parts[0].split("::")[1].strip()
    variant = parts[1].split("::")[1].split("(")[0].split(",")[0].strip()
    variant_pos = find_variant_in_enum(content, enums.get(is_in_enum), variant)
    if variant_pos is None:
        print("Cannot find `{}` in enum `{}`, putting doc aliases on implementation".format(variant, is_in_enum))
        return 0
    alias = '#[doc(alias = "{}")]'.format(ffi_variant)
    if need_doc_alias(content, variant_pos, alias):
        spaces = generate_start_spaces(content[variant_pos], content[variant_pos].strip())
        content.insert(variant_pos, spaces + alias)
        return 1
    return 0


def add_parts(path):
    print("=> Updating '{}'".format(path))
    with open(path, 'r') as f:
        content = f.read().split('\n')

    # The key is the trait name, the value is its line number.
    traits = {}
    # The key is the enum name, the value is its line number.
    enums = {}

    original_len = len(content)
    x = 0
    is_in_trait = None
    is_in_enum = None

    while x < len(content):
        clean = content[x].lstrip()
        if not clean.startswith("pub fn") and not clean.startswith("fn") and " => " not in clean:
            if content[x] == "}":
                is_in_trait = None
                is_in_enum = None
            elif (clean.startswith("impl ") or clean.startswith("impl<")) and " for " in clean:
                parts = clean.split(" for ")
                trait_name = parts[0].split(" ")[-1].strip()
                ty_name = parts[1].split(" ")[0].split("<")[0].strip()
                if trait_name.endswith("Ext") or trait_name.endswith("ExtManual"):
                    is_in_trait = trait_name
                elif ty_name in enums:
                    is_in_enum = ty_name
            # This is needed because we want to put Ext traits doc aliases on the trait methods
            # directly and not on their implementation.
            elif clean.startswith("pub trait") or clean.startswith("trait"):
                name = clean.split("trait")[1].split("<")[0].split(":")[0].split("{")[0].strip()
                if name.endswith("Ext") or name.endswith("ExtManual"):
                    traits[name] = x
                    # Completely skip the trait declaration.
                    while x < len(content) and content[x] != "}":
                        x += 1
                    continue
            elif clean.startswith("pub enum"):
                name = clean[len("pub enum"):].split("<")[0].split("{")[0].strip()
                enums[name] = x
                # Completely skip the enum declaration.
                while x < len(content) and content[x] != "}":
                    x += 1
                continue
            x += 1
            continue
        elif clean.endswith(';'): # very likely a trait method declaration.
            x += 1
            continue

        added = 0
        need_pos_update = False

        fn_name = get_fn_name(clean)
        if fn_name is None:
            x += 1
            continue
        spaces = generate_start_spaces(content[x], clean)
        spaces_and_braces = spaces + '}'
        start = x
        if is_in_trait is not None:
            trait_method_pos = find_method_in_trait(content, traits.get(is_in_trait), fn_name)
            if trait_method_pos is None:
                print("Cannot find `{}` in trait `{}`, putting doc aliases on implementation".format(fn_name, is_in_trait))
            else:
                start = trait_method_pos
                need_pos_update = True
        x += 1
        while x < len(content):
            if content[x] == spaces_and_braces:
                break
            if "ffi::" in content[x]:
                clean = content[x].strip()
                sys_name = get_sys_name(content[x])
                if is_valid_name(sys_name):
                    # Function/method part
                    # FIXME: might be nice to maybe add a configuration file for such cases...
                    if (sys_name != "gtk_is_initialized" or fn_name != "init"):
                        alias = '#[doc(alias = "{}")]'.format(sys_name)
                        if need_doc_alias(content, start, alias) and fn_name in sys_name:
                            content.insert(start, spaces + alias)
                            added += 1
                            start += 1
                            x += 1
                elif is_in_enum is not None and " => " in clean and clean.startswith("ffi::"):
                    # Enum part
                    need_pos_update = True
                    tmp = add_variant_doc_alias(content, clean, enums, is_in_enum)
                    added += tmp
                    x += tmp
            x += 1

        if need_pos_update and added > 0:
            # move their start pos
            for trait in traits:
                if traits[trait] > start:
                    traits[trait] += added
            for enum in enums:
                if enums[enum] > start:
                    enums[enum] += added
        x += 1
    # No need to re-write the file if nothing was changed.
    if len(content) != original_len:
        with open(path, 'w') as f:
            f.write('\n'.join(content))
    return len(content) - original_len


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