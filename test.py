import termtower;

class MockPluginInline:
    def __init__(self) -> None:
        pass

    def is_supported(self, server, language):
        return language == 'itakeinline'

    def start_shell(self, server, language):
        return "itakeinline {{ profile.content }}"

    def get_bootstrap(self, server, language):
        return "itakeinline_bootstrap"

    def refer_argument_script(self, server, language):
        return "itakeinline_script_ref"

    def create_temp_file(self, server, language):
        return "create itakeinline_file"

    def refer_temp_file(self, server, language):
        return "itakeinline_file"

    def delete_temp_file(self, server, language):
        return "delete itakeinline_file"

    def get_profile(self, server, language):
        return "itakeinline_profile"

class MockPluginFilename:
    def __init__(self) -> None:
        pass

    def is_supported(self, server, language):
        return language == 'itakefilename'

    def start_shell(self, server, language):
        return "itakefilename {{ profile.file }}"

    def get_bootstrap(self, server, language):
        return "itakefilename_bootstrap"

    def refer_argument_script(self, server, language):
        return "itakefilename_script_ref"

    def create_temp_file(self, server, language):
        return "create itakefilename_file"

    def refer_temp_file(self, server, language):
        return "itakefilename_file"

    def delete_temp_file(self, server, language):
        return "delete itakefilename_file"

    def get_profile(self, server, language):
        return "itakefilename_profile"

assert termtower.health_check() == "ok"

termtower.include_plugin(MockPluginInline())
termtower.include_plugin(MockPluginFilename())

assert termtower.get_bootstrap_script("itakeinline") == "itakeinline_bootstrap\nitakeinline itakeinline_script_ref"

assert termtower.get_bootstrap_script("itakeinline", "itakefilename") == "itakeinline_bootstrap\ncreate itakeinline_file\nitakefilename itakeinline_file\ndelete itakeinline_file"

assert termtower.get_bootstrap_script("itakefilename", "itakeinline") == "itakefilename_bootstrap\nitakeinline itakefilename_script_ref"

assert termtower.get_bootstrap_script("itakefilename") == "itakefilename_bootstrap\ncreate itakefilename_file\nitakefilename itakefilename_file\ndelete itakefilename_file"

try:
    termtower.get_bootstrap_script("non-existing language")
    raise AssertionError("No error was raised when language is unsupported")
except ValueError:
    pass

print("#!/bin/bash")
print(termtower.get_bootstrap_script("ksh"))
print('----')
print(termtower.get_profile_script("ksh"))
