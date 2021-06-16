# nested templating

end_scope = '@$(superspecial_end_marker;)$@'

class ParseError(Exception):
    def __init__(self, msg) -> None:
        self.message = msg

def process(template, handlers):
    head = 0
    stack = [[]]

    if '^' in handlers:
        stack[0] += handlers['^'](template)

    while head < len(template):
        char = template[head]
        if char == '{':
            stack.append([])
        elif char == '}':
            scope = ''.join(stack.pop())
            split = scope.split(':', 1)
            try:
                if len(split) > 1:
                    stack[-1] += handlers[split[0]](split[1])
                else:
                    stack[-1] += handlers[split[0]]()
            except Exception as err:
                raise ParseError(f"scope: '{scope}'")
        elif char == '\\':
            head += 1
            if head < len(template):
                stack[-1].append(template[head])
        else:
            stack[-1].append(char)
        head += 1

    result = ''.join(stack[0])

    if '$' in handlers:
        result = ''.join(handlers['$'](result))
    
    return result


def subst_red(content):
    content = content.replace(end_scope, '[31m')
    return ['[31m', content, end_scope]

def subst_green(content):
    content = content.replace(end_scope, '[32m')
    return ['[32m', content, end_scope]

def subst_blue(content):
    content = content.replace(end_scope, '[34m')
    return ['[34m', content, end_scope]

def subst_grey(content):
    content = content.replace(end_scope, '[1;30m')
    return ['[1;30m', content, end_scope]

def subst_clr(content):
    content = content.replace(end_scope, '[0m')
    return ['[0m', content, end_scope]

def subst_end(content):
    return [content.replace(end_scope, '[0m')]

subst_lookup = dict(
    red = subst_red,
    green = subst_green,
    blue = subst_blue,
    grey = subst_grey,
    clr = subst_clr
)
subst_lookup['$'] = subst_end


if __name__ == '__main__':
    def demo(template):
        result = process(template, subst_lookup)
        print(f"{template} => \"{result}\"")

    demo('{red:1}{green:2}{blue:3}')
    demo('{red:\}}\\')
    demo('{red:({clr:o})}')
