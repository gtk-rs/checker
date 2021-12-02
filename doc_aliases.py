# pylint: disable=C0114,C0116,R1702,R0912,R0913,R0914,R0915,W0511,W0703

import os
import sys


IGNORE_C_FNS = [
    "_get_reference_count", "_status", "_free", "_destroy", "_unref", "gdk_device_free_history",
]
IGNORE_FNS = [
    "deref", "deref_mut", "drop", "fmt", "clone", "to_value", "g_value_get_flags",
    "g_value_set_flags", "get_type",
]
IGNORE_FNS_START = ["into_glib", "to_glib", "from_glib", "from_raw", "to_raw"]


def is_valid_name(name):
    for char in name:
        if not char.isalnum() and char != '_':
            return False
    for c_fn in IGNORE_C_FNS:
        if name.endswith(c_fn):
            return False
    for fn_start in IGNORE_FNS_START:
        if name.startswith(fn_start):
            return False
    if name in IGNORE_FNS:
        return False
    return True


def get_fn_name(line):
    parts = line.split(" ")
    pos = 0
    while pos < len(parts) and parts[pos] != "fn":
        pos += 1
    pos += 1
    if pos >= len(parts):
        return None
    return parts[pos].split("<")[0].split("(")[0]


# This to prevent to add the same doc alias more than once on a same function.
def need_doc_alias(content, pos, alias):
    pos -= 1
    while pos >= 0:
        stripped = content[pos].strip()
        if not stripped.startswith("#[") and not stripped.startswith("//"):
            return True
        if stripped == alias:
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


def add_variant_doc_alias(content, clean, ffi_first, current_info):
    is_in_enum = current_info["is_in_enum"]
    parts = clean.split(" => ")
    part_a = parts[0].split("::")[1].strip()
    part_b = parts[1].split("::")[1].split("(")[0].split(",")[0].strip()
    if ffi_first:
        if "ffi::" not in parts[0]:
            return 0
        ffi_variant = part_a
        variant = part_b
    else:
        if "ffi::" not in parts[1]:
            return 0
        ffi_variant = part_b
        variant = part_a
    variant_pos = find_variant_in_enum(content, current_info["enums"].get(is_in_enum), variant)
    if variant_pos is None:
        print(f"Cannot find `{variant}` in enum `{is_in_enum}`, ignoring it...")
        return 0
    alias = f'#[doc(alias = "{ffi_variant}")]'
    if current_info["ignore_next"] is False and need_doc_alias(content, variant_pos, alias):
        spaces = generate_start_spaces(content[variant_pos], content[variant_pos].strip())
        content.insert(variant_pos, spaces + alias)
        return 1
    current_info["ignore_next"] = False
    return 0


def update_positions_of(pos_of, start, added):
    for elem in pos_of:
        if pos_of[elem] >= start:
            pos_of[elem] += added


def update_positions(current_info, start, added):
    if added > 0:
        # move their start pos
        update_positions_of(current_info["traits"], start, added)
        update_positions_of(current_info["enums"], start, added)
        update_positions_of(current_info["structs"], start, added)


def add_doc_alias_if_needed(content, start, alias, current_info):
    if current_info["ignore_next"] is False and need_doc_alias(content, start, alias):
        spaces = generate_start_spaces(content[start], content[start].strip())
        content.insert(start, spaces + alias)
        update_positions(current_info, start, 1)
        current_info["pos"] += 1
    current_info["ignore_next"] = False


def handle_annotation(clean, current_info):
    if clean == "// checker-ignore-item":
        current_info["ignore_next"] = True
        return False
    path = current_info["path"]
    pos = current_info["pos"]
    print(f'[{path}:{pos}] Found unknown `checker` command: `{clean[3:]}`')
    current_info["errors"] += 1
    return True


def handle_general_code(content, clean, current_info):
    if content[current_info["pos"]] == "}":
        current_info["is_in_trait"] = None
        current_info["is_in_enum"] = None
    elif current_info["is_in_struct"] == content[current_info["pos"]]:
        current_info["is_in_struct"] = None
    elif (clean.startswith("impl ") or clean.startswith("impl<")) and " for " in clean:
        parts = clean.split(" for ")
        if clean.startswith("impl<"):
            # In here we need to get past the generics of the impl
            pos = len("impl<")
            count = 1
            while count > 0 and pos < len(clean):
                if clean[pos] == "<":
                    count += 1
                elif clean[pos] == ">":
                    count -= 1
                pos += 1
            clean = parts[0][pos:].strip()
        else:
            clean = parts[0][len("impl "):]
        trait_name = clean.split("<")[0].strip()
        ty_name = parts[1].split(" ")[0].split("<")[0].strip()
        if trait_name.endswith("Ext") or trait_name.endswith("ExtManual"):
            current_info["is_in_trait"] = trait_name
        elif ty_name in current_info["enums"]:
            current_info["is_in_enum"] = ty_name
        # Trying to get the doc alias from the
        # `impl From<PdfMetadata> for ffi::cairo_pdf_metadata_t`
        if trait_name == "From" and ty_name.startswith("ffi::"):
            impl_for = parts[0].split("From<")[-1].split(">")[0].strip()
            tmp = None
            for kind in [current_info["structs"], current_info["enums"]]:
                if impl_for in kind:
                    tmp = kind
                    break
            if tmp is not None:
                alias = f'#[doc(alias = "{ty_name[len("ffi::"):]}")]'
                start = kind[impl_for]
                add_doc_alias_if_needed(content, start, alias, current_info)
        # This is to try to get the FFI name from the `FromGlib<ffi::whatever>`.
        elif trait_name.startswith("FromGlib") and "ffi::" in clean:
            tmp = None
            for kind in [current_info["structs"], current_info["enums"]]:
                if ty_name in kind:
                    tmp = kind
                    break
            if tmp is not None:
                ffi_name = clean.split("ffi::")[1].split(">")[0].split(",")[0].strip()
                alias = f'#[doc(alias = "{ffi_name}")]'
                start = kind[ty_name]
                add_doc_alias_if_needed(content, start, alias, current_info)
    # This is needed because we want to put Ext traits doc aliases on the trait methods
    # directly and not on their implementation.
    elif clean.startswith("pub trait") or clean.startswith("trait"):
        name = clean.split("trait")[1].split("<")[0].split(":")[0].split("{")[0].strip()
        if name.endswith("Ext") or name.endswith("ExtManual"):
            current_info["traits"][name] = current_info["pos"]
            # Completely skip the trait declaration.
            while (current_info["pos"] < len(content) and
                    content[current_info["pos"]] != "}"):
                current_info["pos"] += 1
            return
    elif clean.startswith("pub enum"):
        name = clean[len("pub enum"):].split("<")[0].split("{")[0].strip()
        current_info["enums"][name] = current_info["pos"]
        # Completely skip the enum declaration.
        while current_info["pos"] < len(content) and content[current_info["pos"]] != "}":
            current_info["pos"] += 1
        return
    elif clean.startswith("pub struct "):
        if clean.endswith(");") and "ffi::" in clean:
            # This is newtype like "pub struct Quark(ffi::GQuark);". We want to extract the
            # ffi type and add it as a doc alias.
            name = (clean.split("ffi::")[1]
                .split(");")[0]
                .split(">")[0]
                .split(",")[0]
                .strip())
            alias = f'#[doc(alias = "{name}")]'
            add_doc_alias_if_needed(content, current_info["pos"], alias, current_info)
        else:
            name = (clean.split(' struct ')[1]
                    .split('<')[0]
                    .split(':')[0]
                    .split('{')[0]
                    .strip())
            current_info["structs"][name] = current_info["pos"]
            current_info["is_in_struct"] = generate_start_spaces(
                content[current_info["pos"]], clean) + '}'
    elif current_info["is_in_struct"] is not None and clean.startswith("const "):
        # Bitfield declaration handling!
        ffi_name = clean.split(" = ")[-1].split(";")[0].split(" ")[0]
        if "ffi::" in ffi_name:
            ffi_name = ffi_name.split("ffi::")[-1].strip()
            alias = f'#[doc(alias = "{ffi_name}")]'
            add_doc_alias_if_needed(content, current_info["pos"], alias, current_info)
    elif (clean.startswith("pub const ") and
            not clean.startswith("pub const fn ") and
            not clean.startswith("pub const unsafe fn ")):
        name = clean.split("pub const ")[1].split(":")[0]
        whole_const = ""
        start = current_info["pos"]
        while current_info["pos"] < len(content):
            whole_const += content[current_info["pos"]].strip()
            if content[current_info["pos"]].endswith(";"):
                break
            current_info["pos"] += 1
        if "ffi::" in whole_const:
            ffi_name = whole_const.split("ffi::")[1].split(")")[0].split(";")[0].split("}")[0]
            alias = f'#[doc(alias = "{ffi_name}")]'
            add_doc_alias_if_needed(content, start, alias, current_info)
    current_info["pos"] += 1


def look_for_change(content, clean, current_info):
    added = 0
    need_pos_update = False

    fn_name = get_fn_name(clean)
    if fn_name is None:
        current_info["pos"] += 1
        return
    spaces = generate_start_spaces(content[current_info["pos"]], clean)
    spaces_and_braces = spaces + '}'
    start = current_info["pos"]
    if current_info["is_in_trait"] is not None:
        trait_method_pos = find_method_in_trait(
            content, current_info["traits"].get(current_info["is_in_trait"]), fn_name)
        if trait_method_pos is None:
            trait = current_info["is_in_trait"]
            print(
                f"Cannot find `{fn_name}` in trait `{trait}`, putting doc aliases on \
                  implementation")
        else:
            start = trait_method_pos
            need_pos_update = True
    current_info["pos"] += 1
    while current_info["pos"] < len(content):
        if content[current_info["pos"]] == spaces_and_braces:
            current_info["ignore_next"] = False
            break
        if "ffi::" in content[current_info["pos"]]:
            clean = content[current_info["pos"]].strip()
            sys_name = get_sys_name(content[current_info["pos"]])
            if is_valid_name(sys_name):
                # Function/method part
                # FIXME: might be nice to maybe add a configuration file for such cases...
                if (sys_name != "gtk_is_initialized" or fn_name != "init"):
                    alias = f'#[doc(alias = "{sys_name}")]'
                    if (current_info["ignore_next"] is False and
                            need_doc_alias(content, start, alias) and
                            fn_name in sys_name):
                        content.insert(start, spaces + alias)
                        added += 1
                        start += 1
                        current_info["pos"] += 1
            elif current_info["is_in_enum"] is not None and " => " in clean:
                # Enum part
                need_pos_update = True
                tmp = 0
                if clean.startswith("ffi::"):
                    # This is for the "form": "ffi::whatever => Self::Whatever"
                    tmp = add_variant_doc_alias(
                        content, clean, True, current_info)
                elif (clean.startswith("Self::") or
                        clean.startswith(current_info["is_in_enum"] + "::")):
                    # This is for the "form": "Self::Whatever => ffi::whatever"
                    tmp = add_variant_doc_alias(
                        content, clean, False, current_info)
                added += tmp
                current_info["pos"] += tmp
        current_info["pos"] += 1

    if need_pos_update:
        update_positions(current_info, start, added)
    current_info["pos"] += 1


def add_parts(path):
    print(f"=> Updating '{path}'")
    try:
        with open(path, 'r', encoding='UTF-8') as file:
            content = file.read().split('\n')
    except Exception as err:
        print(f"Failed to open `{path}`: {err}")
        return (0, 1)

    original_len = len(content)
    current_info = {
        "path": path,
        # The key is the enum name, the value is its line number.
        "enums": {},
        # The key is the trait name, the value is its line number.
        "traits": {},
        # The key is the enum name, the value is its line number.
        "structs": {},
        "pos": 0,
        "ignore_next": False,
        "errors": 0,
        "is_in_trait": None,
        "is_in_enum": None,
        # In case we are in a "impl X {" block.
        "is_in_simple_impl": None,
        # In this case, it's mostly used for bitfields, so the value will be something like "    }"
        # to know when we leave the struct declaration.
        "is_in_struct": None,
    }

    while current_info["pos"] < len(content):
        clean = content[current_info["pos"]].lstrip()
        if clean.startswith("// checker-"):
            if handle_annotation(clean, current_info):
                break
        elif not clean.startswith("pub fn") and not clean.startswith("fn") and " => " not in clean:
            handle_general_code(content, clean, current_info)
            continue
        elif clean.endswith(';'): # very likely a trait method declaration.
            current_info["pos"] += 1
            continue
        look_for_change(content, clean, current_info)

    # No need to re-write the file if nothing was changed or if an error occurred.
    if current_info["errors"] == 0 and len(content) != original_len:
        with open(path, 'w', encoding='UTF-8') as file:
            file.write('\n'.join(content))
    return (len(content) - original_len, current_info["errors"])


def run_dirs(path):
    errors = 0
    doc_alias_added = 0
    for entry in os.listdir(path):
        full = os.path.join(path, entry)
        if os.path.isdir(full):
            # We don't want to go in auto code parts. They already have everything they need.
            if not entry in ["auto", "subclass"]:
                ret = run_dirs(full)
                doc_alias_added += ret[0]
                errors += ret[1]
        elif entry.endswith(".rs"):
            ret = add_parts(full)
            doc_alias_added += ret[0]
            errors += ret[1]
        if errors != 0:
            break
    return (doc_alias_added, errors)


def main():
    doc_alias_added = 0
    errors = 0
    if len(sys.argv) < 2:
        print("No folder given as argument, updating current `src` (if any)")
        doc_alias_added = run_dirs("src")
    else:
        for entry in sys.argv[1:]:
            if os.path.isdir(entry):
                print(f"> Going into folder `{entry}`...")
                ret = run_dirs(entry)
                doc_alias_added += ret[0]
                errors += ret[1]
                if errors == 0:
                    print("< Done!")
            else:
                ret = add_parts(entry)
                doc_alias_added += ret[0]
                errors += ret[1]
            if errors > 0:
                print("An error occurred, aborting...")
    print("")
    if errors == 0:
        print(f"Added {doc_alias_added} doc aliases.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
