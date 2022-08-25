import os
import textwrap
import re
import json
from tree_sitter import Language, Parser
from fuzzywuzzy import fuzz
from fuzzywuzzy import process

Language.build_library(
    # Store the library in the `build` directory
    'build/my-languages.so',

    # Include one or more languages
    # Jonas
    #[
    # '/Users/jonas/Documents/GitHub/tree-sitter-cpp',
    # '/Users/jonas/Documents/GitHub/tree-sitter-java',
    # '/Users/jonas/Documents/GitHub/tree-sitter-python'
    #]
    # Vivian
    [
        '/home/vivi/src/tree-sitter-python',
        '/home/vivi/src/tree-sitter-java',
        '/home/vivi/src/tree-sitter-cpp'
    ]
)

PY_LANGUAGE = Language('build/my-languages.so', 'python')
JV_LANGUAGE = Language('build/my-languages.so', 'java')
CPP_LANGUAGE = Language('build/my-languages.so', 'cpp')

PYTHON = "PYTHON"
JAVA = "JAVA"
CPP = "CPP"

types = ["int", "float", "double", "boolean", "bool", "string", "String","class","public","void"]

operators = [["==", "!=", ">=", "<=", ">", "<"],  # comparison
             ["++", "+=", "+", "--", "-=", "-", "//",
                 "/=", "/", "%=", "%", "**", "*=", "*"],
             # arithmetic and assignment
             ["&&", "||", "!", "and", "or", "not"],  # logical
             ["is not", "is"],  # identity
             ["not in", "in"]  # membership
             ]

files = ["simple", "if", "while","for","break"]#, "ifelse","ifvar", "op", "sum_two_num"]  # parallel corpus



# Create Parsers for the three languages
parser_py = Parser()
parser_py.set_language(PY_LANGUAGE)

parser_jv = Parser()
parser_jv.set_language(JV_LANGUAGE)

parser_cpp = Parser()
parser_cpp.set_language(CPP_LANGUAGE)


class RuleSet:
    """class for the database maintaining the translations rules"""

    def __init__(self):
        if not os.path.isfile("rules.json"):
            self.rules = {}
        else:
            with open("rules.json", encoding="utf8") as file:
                self.rules = json.load(file)
                print(f"Loading {len(self.rules)} rules ... Done ...")

        with open("keywords_lookup.json", encoding="utf8") as file:
            self.keywords = json.load(file)

        if not os.path.isfile("keywords_treesitter.txt"):
            self.tree_keywords = []
        else:
            with open("keywords_treesitter.txt", encoding="utf8") as file:
                self.tree_keywords = file.read().split(",")
                print(f"Loading {len(self.tree_keywords)} keywords for parse tree ... Done ...")


    def save_rules(self):
        """store derived rules in json format"""
        with open("rules.json", "a+", encoding="utf8") as file:
            file.truncate(0)
            file.seek(0)
            json.dump(self.rules, file, indent=4)


    def save_keywords(self):
        """store keywords from tree-sitter"""
        with open("keywords_treesitter.txt", "a+", encoding="utf8") as file:
            file.truncate(0)
            file.seek(0)
            length = len(self.tree_keywords) - 1
            for i, keyword in enumerate(self.tree_keywords):
                if i == length:
                    file.write(keyword)
                else:
                    file.write(keyword + ",")


    def check_for_keyword(self, parse_tree_sexp, parse_tree, single_line=False):
        """return keyword from the tree-sitter parse tree"""
        if "ERROR" in parse_tree_sexp:
            return "ERROR"
        if single_line and "MISSING" in parse_tree_sexp:
            return "MISSING"

        root_node = parse_tree.root_node
        if root_node.children:
            if root_node.children[0].type not in self.tree_keywords:
                self.tree_keywords.append(root_node.children[0].type)  # add it
            return str(root_node.children[0].type)
        return ""


    def create_generic_expression(self, code, language=CPP.lower()):
        """return generic expression for given code line"""
        generic_code = code
        in_keywords, names = extract_name(self, code)

        if in_keywords:
            return self.keywords[names][language]
        if names:
            generic_code = re.sub(r"([^<<])(\")([^\"]*)(\")([;|\n]+)", r"\1'\3'\5", generic_code) # replace "" with ''
            for name in names:
                generic_code = re.sub(rf"\b{name}\b", "name", generic_code)

        values = extract_value(code)
        if values:
            for value in values:
                generic_code = generic_code.replace(value[0], "value", value[1])

        variable_type = extract_type(code)
        if variable_type:
            generic_code = re.sub(rf"\b{variable_type}\b", "type", generic_code)

        operators = extract_operator(code)
        if operators:
            for operator in operators:
                generic_code = generic_code.replace(operator, "operator")

        return generic_code


    def extend_rule(self, cpp, java, python, key):
        """extend existing rule '<key>' by list of generic expressions, one for each language"""
        generic_cpp = self.create_generic_expression(cpp)
        generic_jv = self.create_generic_expression(java, JAVA.lower())
        generic_py = self.create_generic_expression(python, PYTHON.lower())

        if generic_cpp and len(generic_cpp) - len(generic_cpp.lstrip()) == 0 and generic_jv and generic_py:
            flag = False

            for entry in self.rules[key]:
                if generic_cpp in entry:
                    flag = True
                    break  # already present

            if not flag:
                self.rules[key].append([generic_cpp, generic_jv, generic_py])


    def add_rule(self, cpp, java, python, key):
        """add new translation rule to the database"""
        generic_cpp = self.create_generic_expression(cpp)
        generic_jv = self.create_generic_expression(java, JAVA.lower())
        generic_py = self.create_generic_expression(python, PYTHON.lower())

        if generic_cpp and generic_jv and generic_py:
            self.rules.update({key: [[generic_cpp, generic_jv, generic_py]]})


    def user_input(self, keyword=None):
        """Ask the user for a rule"""
        print("Please enter your code below")
        print("Please try to consider newlines and indents for better accuracy in translations")
        cpp = input("CPP: ")
        java = input("JAVA: ")
        python = input("PYTHON: ")

        if keyword in self.rules.keys():
            self.extend_rule(cpp, java, python, keyword)
        else:
            self.add_rule(cpp, java, python, keyword)

        print("Rule is successfully added...")


    def determine_statement(self, keyword, parallel_files, languages):
        """determine statements in the tree-sitter parse tree"""
        generic_statements = []

        for file, language in zip(parallel_files, languages):
            with open(file, 'r+', encoding="utf8") as f:
                lines = f.readlines()
            for line in lines:
                tree_sexp, tree = create_parse_tree(line, language)
                if self.check_for_keyword(tree_sexp, tree) == keyword:
                    generic_statements.append(create_generic_statement(lines, line, language)[0])

        return generic_statements


    def derive_rules(self, corpus):
        """derive rules based of parallel corpus"""
        for file in corpus:
            with open("data/parallel_corpus/python/" + file + ".py", 'r', encoding="utf8") as python, open(
                    "data/parallel_corpus/java/" + file + ".java", 'r', encoding="utf8") as java, open(
                    "data/parallel_corpus/cpp/" + file + ".cpp", "r", encoding="utf8") as cpp:
                # lines should match
                for line_py, line_jv, line_cpp in zip(python, java, cpp):
                    tree_sexp, tree = create_parse_tree(line_jv, JAVA)
                    keyword = self.check_for_keyword(tree_sexp, tree)

                    if keyword in ["if_statement", "while_statement", "for_statement"]:
                        if keyword not in self.rules.keys():
                            self.rules.update({keyword: [
                                self.determine_statement(keyword, ["data/parallel_corpus/cpp/" + file + ".cpp",
                                                         "data/parallel_corpus/java/" + file + ".java",
                                                         "data/parallel_corpus/python/" + file + ".py"],
                                                         [CPP, JAVA, PYTHON] )
                                                        ]
                                                })

                    elif keyword and keyword != "ERROR":
                        best_match = process.extractOne(keyword, self.rules.keys(), scorer=fuzz.partial_ratio)
                        if not best_match or best_match[-1] != 100:
                            self.add_rule(line_cpp, line_jv, line_py, keyword)
                        else:
                            self.extend_rule(line_cpp, line_jv, line_py, best_match[0])

                        tree_sexp_py, tree_py = create_parse_tree(line_py, PYTHON)  # since sometimes differ
                        keyword_py = self.check_for_keyword(tree_sexp_py, tree_py)
                        if keyword_py and keyword_py != "ERROR" and fuzz.partial_ratio(keyword_py, keyword) != 100:
                            best_match_py = process.extractOne(keyword_py, self.rules.keys(), scorer=fuzz.partial_ratio)
                            if not best_match_py or best_match_py[-1] != 100:
                                self.add_rule(line_cpp, line_jv,
                                              line_py, keyword_py)
                            else:
                                self.extend_rule(line_cpp, line_jv, line_py, best_match_py[0])


    def translate_file(self, file_name, language):
        """translate given input file"""
        translations = []
        with open(file_name, 'r+', encoding="utf8") as file:
            code_lines = file.readlines()

        j = -1 # tracking code blocks like if_statements

        for i, line in enumerate(code_lines):
            if j >= i:
                continue

            tree_sexp, tree = create_parse_tree(line, language)
            keyword = self.check_for_keyword(tree_sexp, tree)
            if keyword in ["if_statement", "while_statement", "for_statement"] and keyword in self.rules.keys():
                generic_statement, statement, j, else_index = create_generic_statement(code_lines, line, language)

                index = 0
                if language == JAVA:
                    index = 1
                elif language == PYTHON:
                    index = 2
                entry_match = process.extractOne(generic_statement,
                                                 {k: entry[index] for k, entry in enumerate(self.rules[keyword])},
                                                 scorer=fuzz.ratio)

                if entry_match[1] == 100:
                    translations.append(self.transform_statement(self.rules[keyword][entry_match[-1]], statement, language, else_index))

            elif keyword and keyword not in ["ERROR"]:
                best_match = process.extractOne(keyword, self.rules.keys(), scorer=fuzz.partial_ratio)
                if best_match[-1] == 100:
                    flag = False
                    index = 0
                    if language == JAVA:
                        index = 1
                    elif language == PYTHON:
                        index = 2
                    for entry in self.rules[best_match[0]]:
                        if self.create_generic_expression(line, language.lower()) == entry[index]:
                            translations.append(self.transform(entry, line))
                            flag = True
                            break
                    if not flag:
                        print(f"No appropriate transformation for {best_match[0], self.create_generic_expression(line, language.lower())} was found in the database...do you want to add one? y/n")
                        answer = input()
                        if answer == "y":
                            self.user_input(best_match[0])
                        else:
                            pass

                else:
                    answer = input(f"No appropriate rule for {keyword} was found in the database...do you want to add it? y/n")
                    if answer == "y":
                        self.user_input(keyword)
                    else:
                        pass

        return translations


    def translate_line(self, code_input, language):
        """translate single code line"""
        tree_sexp, tree = create_parse_tree(code_input, language)
        keyword = self.check_for_keyword(tree_sexp, tree, single_line=True)

        if keyword not in ["MISSING", "ERROR"]:
            best_match = process.extractOne(keyword, self.rules.keys(), scorer=fuzz.partial_ratio)

            if best_match[-1] == 100:
                index = 0
                if language == JAVA:
                    index = 1
                elif language == PYTHON:
                    index = 2

                entry_match = process.extractOne(self.create_generic_expression(code_input, language.lower()),
                                                 {k: entry[index] for k, entry in enumerate(self.rules[best_match[0]])},
                                                 scorer=fuzz.ratio)

                if entry_match[1] != 100:
                    print(f"The closest matching rule for {code_input} hasn't got ratio 100 -> {best_match[0]}: {entry_match}")

                return self.transform(self.rules[best_match[0]][entry_match[-1]], code_input), False
            return None, False
        return None, True


    def transform_statement(self, generic_expressions, statement, language, else_index=0):
        """transform generic expressions for if_statement or while_statement using input statement"""

        translations = []
        block_in_block = []
        for i, entry in enumerate(generic_expressions):

            if language in [CPP, JAVA]:
                condition = re.findall(r'\(([^()]*)\) \{', statement)
                if len(condition) > 1: # blocks in block
                    temp = statement

                    while re.findall(r'(\{([^{}]*)})', temp):
                        block_in_block.append(re.findall(r'(\{([^{}]*)})', temp)[0][0])
                        temp = temp.replace(re.findall(r'(\{([^{}]*)})', temp)[0][0], "", 1)

                    block = block_in_block[-1].split("\n")  # first block
                    block_in_block.remove(block_in_block[-1]) # subblocks in order

                    condition = condition[0]

                elif condition:
                    condition = condition[0]
                    block = re.findall(r'\{([^}]+)\}', statement)[0].split("\n")

                if else_index:
                    else_block = re.findall(r'} else \{([^}]+)\}', statement)[0].split("\n")

            else:  # PYTHON
                condition = re.findall('([if|while|for]+ (.*):)', statement)

                if len(condition) > 1: # blocks in block
                    for j in range(1, len(condition) + 1):
                        pot_block = statement[statement.index(condition[-j][0]):].split("\n")[1:]
                        indent = (len(pot_block[0]) - len(pot_block[0].lstrip()))
                        extend_blocks = ['']
                        for line in pot_block:
                            if (len(line) - len(line.lstrip())) == indent:
                                if "while" in line or "if" in line:
                                    extend_blocks[-1] = extend_blocks[-1] + str(line[:-1]) + "\n"
                                else:
                                    extend_blocks[-1] = extend_blocks[-1] + str(line) + "\n"
                            elif (len(line) - len(line.lstrip())) < indent:
                                break
                        block_in_block.extend(extend_blocks)

                    block = block_in_block[-1].split("\n")
                    block_in_block.remove(block_in_block[-1])
                    block_in_block = block_in_block[::-1] # reverse -> subblocks in order

                    condition = condition[0][1]

                else:
                    condition = condition[0][1]
                    block = statement[statement.index(":") + 1:].split("\n")
                    if any("else" in line for line in block):
                        # consider only block before else
                        block = block[:["else" in line for line in block].index(True)]

                if else_index:
                    else_block = statement[statement.index(":") + 1:].split("\n")
                    if any("else" in line for line in else_block):
                        # consider only block in else
                        else_block = else_block[["else" in line for line in else_block].index(True)+1:]

            block = [item + "\n" for item in block if textwrap.dedent(item)]

            if else_index:
                else_block = [item + "\n" for item in else_block if textwrap.dedent(item)]

            if ";" in condition and i == 2: # condition in for statement java and cpp
                condition = condition.split(";")
                _, variable = extract_name(self, condition[0])
                start = extract_value(condition[0])[0]
                stop = extract_value(condition[1])[0]
                step = extract_operator(condition[2])
                condition = self.keywords["for"]["python"].replace("variable", variable[0])
                condition = condition.replace("start", start[0])
                condition = condition.replace("stop", stop[0])
                if step[0] == "--":
                    condition = condition.replace("step", "-1")
                elif step[0] == "++":
                    condition = condition.replace("step", "1")
            
            elif "range" in condition and i in [0, 1]: # condition in for statement python
                _, variable = extract_name(self, condition)
                start, stop, step = extract_value(condition)
                sign = extract_operator(condition)
                condition = self.keywords["for"]["cpp"].replace("variable", variable[0])
                condition = condition.replace("start", start[0])
                condition = condition.replace("stop", stop[0])
                if sign and sign[0] == "-":
                    condition = condition.replace("step", "--")
                elif step:
                    condition = condition.replace("step", "++")
                if int(start[0]) > int(stop[0]) and sign and sign[0] == "-":
                    condition = condition.replace("sign", ">")
                else:
                    condition = condition.replace("sign", "<")

            entry = entry.replace("@", condition, 1)

            # translate the block via rules
            if "@" in entry:
                for line in block:
                    translated_line, missing_flag = self.translate_line(line, language)
                    if missing_flag and len(line) > 2:

                        if language in [CPP, JAVA]:
                            line = line[:-1] + block_in_block[0].split("\n")[0] + line[-1]
                            lines = [line]
                            lines.extend([b + "\n" for b in block_in_block[0].split("\n")[1:]])

                        else:  # PYTHON
                            line = line[:-1] + ":" + line[-1]
                            lines = [line]
                            lines.extend([b + "\n" for b in block_in_block[0].split("\n")])

                        block_in_block.remove(block_in_block[0])

                        tree_sexp, tree = create_parse_tree(line, language)
                        keyword = self.check_for_keyword(tree_sexp, tree)

                        generic_statement, block_statement, _, _ = create_generic_statement(lines, line, language)

                        if fuzz.token_set_ratio(generic_statement, self.rules[keyword][0]) == 100:
                            block_translations = self.transform_statement(self.rules[keyword][0], block_statement, language)

                            for block_line in block_translations[i].split("\n"):
                                entry = re.sub('@', block_line + "\n" + "    @", entry, 1)

                    elif translated_line:
                        entry = re.sub('@', translated_line[i] + "    @", entry, 1)

                entry = re.sub('\n    @', '', entry, 1)

                if else_index:
                    for line in else_block:
                        translated_line, missing_flag = self.translate_line(line, language)
                        entry = re.sub('@', translated_line[i] + "    @", entry, 1)

            entry = re.sub('\n    @', '', entry)
            translations.append(entry)
        return translations


    def replace_token(self, tokens_to_replace, keywords, i, updated_input):
        for index, token in enumerate(tokens_to_replace):
            if i == 0 and token != keywords[index]["cpp"]:
                updated_input = re.sub(token, keywords[index]["cpp"], updated_input)
            elif i == 1 and token != keywords[index]["java"]:
                updated_input = re.sub(token, keywords[index]["java"], updated_input)
            elif i == 2 and token != keywords[index]["python"]:
                updated_input = re.sub(token, keywords[index]["python"], updated_input)
        return updated_input


    def get_tokens_tobe_replaced(self, tokens):
        keywords = []
        tokens_to_replace = []
        for token in tokens:
            best_match = process.extractOne(token, self.keywords.keys(), scorer=fuzz.ratio)
            if best_match[-1] >= 70:
                keywords.append(self.keywords[best_match[0]])
                tokens_to_replace.append(token)
        
        return keywords, tokens_to_replace


    def transform(self, generic_expressions, code):
        """transform generic expressions for single line using the input code line"""
        translations = []
        tokens = code.split()
        keywords, tokens_to_replace = self.get_tokens_tobe_replaced(tokens)

        for i, entry in enumerate(generic_expressions):
            updated_input = code
            if keywords:
                updated_input = self.replace_token(tokens_to_replace, keywords, i, updated_input)

            values = extract_value(updated_input)
            if values:
                for value in values:
                    entry = entry.replace("value", value[0], value[1])

            in_keywords, names = extract_name(self, updated_input)
            if in_keywords:
                if "@" in entry: # print function
                    string_argument = re.findall(r'\(([^\()]*)\)', code) # print argument in java and python
                    if not string_argument:
                        string_argument = re.findall('(?<=<<)(.*)(?=;)', code) # print argument in cpp

                    for string in string_argument:
                        entry = re.sub('@', string + "@", entry)

                    entry = re.sub('@', '', entry)

                    # replace symbols
                    if i == 0: # cpp
                        if "+" in entry:
                            entry = entry.replace('+','<<')
                        elif "," in entry:
                            entry = entry.replace(',','<<')
                    elif i == 1: # java
                        if "<<" in entry:
                            entry = entry.replace('<<','+')
                        elif "," in entry:
                            entry = entry.replace(',','+')
                    elif i == 2: # python
                        if "<<" in entry:
                            entry = entry.replace('<<',',')
                        elif "+" in entry:
                            entry = entry.replace('+',',')
            if names:
                for name in names:
                    entry = entry.replace("name", name, 1)
                if "name" in entry and len(names) == 1:  # when in one language there are less variable names: eg. +b vs. b = +b;
                    entry = entry.replace("name", names[0])

            type = extract_type(updated_input)
            if type in ["bool", "boolean"]:
                best_match = process.extractOne("bool", self.keywords.keys(), scorer=fuzz.ratio)
                if best_match[-1] >= 70:
                    if i == 0:
                        entry = re.sub("type", self.keywords[best_match[0]]["cpp"], entry)
                    elif i == 1:
                        entry = re.sub("type", self.keywords[best_match[0]]["java"], entry)
                    else:
                        entry = re.sub("type", self.keywords[best_match[0]]["python"], entry)

            elif type in ["string", "String"]:
                best_match = process.extractOne("stringString", self.keywords.keys(), scorer=fuzz.ratio)
                if best_match[-1] >= 70:
                    if i == 0:
                        entry = re.sub("type", self.keywords[best_match[0]]["cpp"], entry)
                    elif i == 1:
                        entry = re.sub("type", self.keywords[best_match[0]]["java"], entry)
                    else:
                        entry = re.sub("type", self.keywords[best_match[0]]["python"], entry)

            elif type:
                entry = entry.replace("type", type)

            operators = extract_operator(updated_input)
            if operators:
                for operator in operators:
                    entry = entry.replace("operator", operator)

            entry = re.sub(r"([^<<])(\')([^\']*)(\')([;|\n]+)", r'\1"\3"\5', entry) # replace '' with "" (again to original)

            translations.append(entry)

        return translations


def create_parse_tree(input_code, input_language):
    """return s-expression and parse tree for the given code and language using the tree-sitter"""
    if input_language == "CPP":
        return parser_cpp.parse(bytes(input_code, "utf-8")).root_node.sexp(), parser_cpp.parse(bytes(input_code, "utf-8"))
    if input_language == "JAVA":
        return parser_jv.parse(bytes(input_code, "utf-8")).root_node.sexp(), parser_jv.parse(bytes(input_code, "utf-8"))
    return parser_py.parse(bytes(input_code, "utf-8")).root_node.sexp(), parser_py.parse(bytes(input_code, "utf-8"))


def create_generic_statement(lines, line, language=JAVA):
    """return generic expression, source code and end line for if_statement or while_statement"""

    i = lines.index(line)
    lines = list(lines[i + 1:])
    statement = line
    j = 0
    else_index = 0

    # CPP and JAVA
    if language in [CPP, JAVA]:
        return create_generic_statement_cpp_java(i, lines, line, statement, j, else_index, language)

    # PYTHON
    return create_generic_statement_python(i, lines, line, statement, j, else_index)


def create_generic_statement_cpp_java(i, lines, line, statement, j, else_index, language):
    """return generic expression, source code and end line for if_statement or while_statement from cpp and java"""
    statement += lines[j]
    while "MISSING" in create_parse_tree(statement, language)[0] or "ERROR" in create_parse_tree(statement, language)[0] or (j+1 < len(lines) and "else" in lines[j+1]):
        j += 1
        statement += lines[j]  # completing
        if "else" in lines[j]:
            else_index = j

    gen_statement = line

    if else_index:
        gen_statement += (len(lines[j - 1]) - len(lines[j - 1].lstrip())) * " " + "@\n" + lines[else_index]

    gen_statement += (len(lines[j - 1]) - len(lines[j - 1].lstrip())) * " " + "@\n" + lines[j]

    gen_statement = re.sub(r'if \(([^"]*)\)', 'if (@)', gen_statement)
    gen_statement = re.sub(r'while \(([^"]*)\)', 'while (@)', gen_statement)
    gen_statement = re.sub(r'for \(([^"]*)\)', 'for (@)', gen_statement)

    block = re.findall(r'(\{([^{}]*)})', statement)
    temp = statement
    
    # block in block
    while re.findall(r'(\{([^{}]*)})', temp):
        block = re.findall(r'(\{([^{}]*)})', temp)
        temp = temp.replace(re.findall(r'(\{([^{}]*)})', temp)[0][0], "")

    block = block[0][-1].split("\n")
    block = [entry for entry in [textwrap.dedent(item) for item in block if item] if entry]

    return gen_statement, statement, j + 1 + i, else_index


def create_generic_statement_python(i, lines, line, statement, j, else_index):
    """return generic expression, source code and end line for if_statement or while_statement from python"""

    while (j < len(lines) and lines[j] != "\n" and len(lines[j]) - len(lines[j].lstrip()) != 0) or (j < len(lines) and "else" in lines[j]):  # indent
        statement += lines[j]  # completing
        if "else" in lines[j]:
            else_index = j
        j += 1

    gen_statement = line

    gen_statement += lines[j - 1]
    gen_statement = gen_statement.replace(textwrap.dedent(lines[j - 1]), '@\n')

    if else_index:
        gen_statement += lines[else_index]
        gen_statement += lines[else_index + 1]
        gen_statement = gen_statement.replace(textwrap.dedent(lines[else_index + 1]), '@\n')

    gen_statement = re.sub('if (.*):', 'if @:', gen_statement)
    gen_statement = re.sub('while (.*):', 'while @:', gen_statement)
    gen_statement = re.sub('for (.*):', 'for @:', gen_statement)

    return gen_statement, statement, j + i, else_index


def extract_type(input_string):
    """return the type of variable if present, derive it otherwise"""
    string = input_string.split()
    for type in types:
        if type in string:
            return type

    numbers = extract_value(input_string)
    if numbers and len(numbers) == 1:
        if numbers[0][0] in ["true", "false", "True", "False"]:
            return "bool"
        if re.search(r"\.", numbers[0][0]) is None:
            return "int"
        if len(numbers[0][0]) < 9:
            return "float"  # 6-7 significant digits
        return "double"  # 15-16 significant digits

    if numbers:  # more than one extracted value
        flag_float, flag_double = False, False
        for number in numbers:
            if number in ["true", "false", "True", "False"]:
                return "bool"
            if re.search(r"\.", number[0]) is None:
                continue  # int
            if len(number[0]) < 9:
                flag_float = True  # 6-7 significant digits
            else:
                flag_double = True  # 15-16 significant digits
        if flag_double:
            return "double"
        return "float" if flag_float else "int"
    return "string"

def extract_value(input_string):
    """return the values from given input"""
    numbers = re.findall(r'true|false|True|False', input_string)
    string = re.sub('([a-zA-Z]+[_a-zA-Z0-9]*)', '', input_string)
    numbers.extend(re.findall(r'\d+(?:\.\d+)?', string))

    return [(number, numbers.count(number)) for number in numbers] if numbers else None


def extract_name(self, input_string):
    """return variable names from given input"""
    string = re.sub('true|false|True|False', '', input_string)
    string = re.sub(r'\(([^\()]*)\)', '@', string) # print argument in java and python
    string = re.sub(r'(?<=<<)(.*)(?=;)', '@', string)  # print argument in cpp

    tokens = string.split()

    for token in tokens:
        if token in types:
            tokens.remove(token)
        for op_list in operators:
            if token in op_list:
                tokens.remove(token)

    string = " ".join(tokens)
    best_match = process.extractOne(string, self.keywords.keys(), scorer=fuzz.token_set_ratio)
    if best_match[-1] >= 45:
        return True, best_match[0]

    names = re.findall('([a-z,A-Z]+[_]*[a-z,A-Z,0-9]*)*', string)
    return False, [name for name in names if name and name not in types]


def extract_operator(input_string):
    """return operators from given input"""
    op = []
    for group in operators:
        for operator in group:
            if operator in input_string:
                op.append(operator)
    return op if op else None
