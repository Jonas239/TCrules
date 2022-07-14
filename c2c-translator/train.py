import parser
from argparse import ArgumentParser


rule_set = parser.RuleSet()
arg_parser = ArgumentParser()

arg_parser = ArgumentParser()
arg_parser.add_argument("-f", "--file", type=str,
                        help="input file to be translated", metavar="FILE", required=False)
arg_parser.add_argument("-i", "--inputlanguage",
                        choices=["CPP", "JAVA", "PYTHON"], required=False)
arg_parser.add_argument("-t", "--train",type=bool,
                        metavar="TRAIN", help="train parser", required=False)

arguments = arg_parser.parse_args()
source_file = arguments.file
input_language = arguments.inputlanguage
training = arguments.train
user_input_flag = arguments.train


if training:
    rule_set.derive_rules(parser.files)
    rule_set.save_rules()


if source_file:  # translate given file
    translations = rule_set.translate(source_file, input_language)
    for code_line in translations:
        print(code_line)


rule_set.save_keywords()
