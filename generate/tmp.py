#!/usr/bin/env python3

from os import walk
import re

def main():
    _, _, mods_name = next(walk('../src/gen'))
    mod_rs_file = open('../src/gen/mod.rs', 'w+')
    for mod in mods_name:
        if mod == 'mod.rs' or re.match(".*\.rs", mod) == None:
            continue
        mod_name_line = 'pub mod ' + mod[:-3] + ';\n'
        mod_rs_file.write(mod_name_line)
    mod_rs_file.close()

if __name__ == '__main__':
    main()
