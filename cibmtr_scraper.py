import csv
import json
import os
import string

import requests
import tika
from bs4 import BeautifulSoup
import ast
from collections import OrderedDict
from nltk.corpus import stopwords


nlpql_template = '''
// Phenotype library name
phenotype "Form {}, Question {}" version "1";

// # Referenced libraries #
include ClarityCore version "1.0" called Clarity;

// Data Entities
{}

// Operations
{}

// Comments
/*
{}

*/

'''

nlpql_template2 = '''
// Phenotype library name
phenotype "Form {}, Group {}" version "1";

// # Referenced libraries #
include ClarityCore version "1.0" called Clarity;

// Termsets
{}

// Data Entities
{}

// Operations
{}

// Comments
/*
{}

*/

'''

termset_template = '''
termset question_{}_{}_terms: [
    {}
];

'''

provider_assertion_template = '''
define final question_{}_{}_assertion:
    {}
'''


cql_template = '''
library Retrieve2 version '1.0'

using FHIR version '3.0.0'

include FHIRHelpers version '3.0.0' called FHIRHelpers

codesystem "LOINC": 'http://loinc.org'
codesystem "SNOMED-CT": 'urn:oid:2.16.840.1.113883.6.96'
codesystem "RxNorm": 'http://www.nlm.nih.gov/research/umls/rxnorm'

context Patient

{}

{}

'''

# +
cql_concept_template = '''
define "question_%s_%s_concept": Concept {
    %s
}

'''


# -

# Code '26464-8' from "LOINC",
# Code '804-5' from "LOINC",
# Code '6690-2' from "LOINC",
# Code '49498-9' from "LOINC"

# +
cql_result_template = '''
define "question_{}_{}_coded":
    [{}: Code in "question_{}_{}_concept"]
'''


# -

headers = [
    'Key Fields',
    'Product',
    'Survival',
    'Recipient Demographics',
    'Cellular Therapy and HCT History',
    'Product Identification',
    'Indication for Cellular Therapy',
    'Infection',
    'Disease Assessment at Last Evaluation Prior to Cellular Therapy',
    'Systemic Therapy Prior to Cellular Therapy Questions',
    'Functional Status',
    'Comorbid Conditions',
    'Clinical Status of Recipient Prior to the Preparative Regimen (Conditioning)',
    'Organ Function Prior to the Preparative Regimen (Conditioning)',
    'Hematologic Findings Prior to the Preparative Regimen (Conditioning)',
    'Pre-HCT Preparative Regimen (Conditioning)',
    'Socioeconomic Information',
    'Toxicities'
]
pdfs = list()
for file in os.listdir("./cimbtr_forms/"):
    if file.endswith(".txt"):
        pdfs.append(file)

# +
questions_dict = dict()


# -

def question_number(line):
    question_string = ''
    spl = line.split(':')
    try:
        n = int(spl[-1])
    except:
        n = -1

    if len(spl) > 1:
        question_string = spl[0]
    if n != -1 and n < 10000:
        return question_string, n
    else:
        return None, None


def get_pdfs():
    tika.initVM()
    from tika import parser

    page = requests.get('http://www.cibmtr.org/DataManagement/DataCollectionForms/Pages/index.aspx')
    soup = BeautifulSoup(page.text, 'html.parser')

    locs = soup.find_all('a')
    for loc in locs:
        href = loc.get('href', '')
        if href.startswith('javascript:WebForm_DoPostBackWithOptions(new WebForm_PostBackOptions'):
            args = href.split('"')
            for a in args:
                if a.startswith('http') and a.endswith('pdf') and not a.endswith('EC.pdf') and not \
                        a.endswith('+.pdf') and 'Log' not in a:
                    print(a)
                    name = a.split('/')[-1]
                    if name.startswith('Form'):
                        continue
                    response = requests.get(a)

                    pdf_name = './cimbtr_forms/{}'.format(name)
                    with open(pdf_name, 'wb') as f:
                        f.write(response.content)

                    parsed = parser.from_file(pdf_name)
                    with open('./cimbtr_forms/{}.txt'.format(name.split('.')[0]), 'w') as f:
                        f.write(parsed['content'].strip())


def parse_questions():
    forms = {}
    for p in pdfs:
        name = p.split('.')[-2]
        question_dict = {}
        with open('./cimbtr_forms/{}'.format(p), 'r') as txt_file:
            lines = txt_file.readlines()
            questions = list()
            header = 'UNKNOWN'
            txt = ''
            last_question = 0
            for l in lines:
                if len(l.strip()) == 0:
                    continue
                is_header = False
                for h in headers:
                    if l.startswith(h):
                        header = h
                        is_header = True
                        break
                if not is_header:
                    q_text, q_number = question_number(l)
                    if q_number and last_question < q_number and q_number > 1:
                        last_question = q_number
                        if len(txt) > 0:
                            out_txt = "{} {}\n\n{}".format(q_number, q_text, txt)
                            question_dict[q_number] = out_txt
                        # print('is_a_new_question', q_number)
                        txt = ''
                    else:
                        txt += l

        forms[name] = question_dict
    return forms


def stubs(form="4100R4", form_data=None):
    if not form_data:
        form_data = dict()

    form_questions = form_data[form]
    if not form_questions:
        form_questions = dict()
    new_dir = '/Users/charityhilton/repos/CIBMTRaaS/forms/{}/'.format(form)
    if not os.path.exists(new_dir):
        os.makedirs(new_dir)

    max_questions = 300
    keys = list(form_questions.keys())
    if len(keys) > 0:
        max_questions = max(keys) + 1
    for i in range(1, max_questions):
        print('form {}, question {}'.format(file, i))
        with open('/Users/charityhilton/repos/CIBMTRaaS/forms/{}/question_{}.nlpql'.format(form, i), 'w') as f:
            entities = ""
            operations = ""
            if i in form_questions:
                comments = form_questions[i]
            else:
                comments = ""
            f.write(nlpql_template.format(form, i, entities, operations, comments))



# +
def value_set(set_name, final_str, *args):
    
    args_str = '{ \n \t\t'
    
    for k,v in args[0].items():

        if isinstance(v, float):
            v = '"{}"'.format(v)

        args_str += '{}: {}, \n \t\t'.format(k,v)
        
    args_str += "}"

    val_set = """
    define {}:
        Clarity.ValueExtraction({});         
    """.format(set_name, args_str)
    
    val_set += final_str

    
    return val_set
    
def gen_feature_name(rhs, comparator, lhs):
        
    op_name = "AnyVal"

    if comparator == "<":
        op_name = "Lt"
    elif comparator == ">":
        op_name = "Gt"

    elif comparator == "<=":
        op_name = "Leq"

    elif comparator == ">=":
        op_name = "Geq"

    elif comparator == "==":
        op_name = "Equals"

    feature_name = "{}{}{}".format(rhs[0], op_name, str(lhs))
    
    final_str = """
        
    define final has{}:
        where {}.value {} {};
    
    """.format(feature_name, feature_name, comparator, lhs) 
    
    return feature_name, final_str

def convert_expr_to_value_extraction(expr, feature_name = None):

    kwargs_to_pass = {}
    
    val_extr_ast = ast.parse(expr)

    code_ast = ast.parse(expr)
    
    lhs = list()
    rhs = None
    comparator = None
    
    for node in ast.walk(code_ast):
        # we need to be able to handle n-grams that are actually a single concept/measurement, etc.
        if isinstance(node, ast.Name):
            lhs.append(node.id)
        
        # this is our (numeric) LHS
        elif isinstance(node, ast.Num):
            rhs = node.n
            
         # grab our operator and convert it to a string representation   
        elif isinstance(node, ast.Compare):
            op = node.ops[0]
            if isinstance(op, ast.Lt):
                comparator = "<"
            elif isinstance(op, ast.Gt):
                comparator = ">"
            elif isinstance(op, ast.LtE):
                comparator = "<="
            elif isinstance(op, ast.GtE):
                comparator = ">="
            elif isinstance(op, ast.Eq):
                comparator = "=="

    kwargs_to_pass["termset"] = "{}".format([x.replace("_", " ") for x in lhs])
    
    # leq and geq are handled the same as >; < per clarity value extraction docs
    if comparator in ("<", "<="):
        kwargs_to_pass["maximum_value"] = '"{}"'.format(rhs)
    elif comparator in (">", ">="):
        kwargs_to_pass["minimum_value"] = '"{}"'.format(rhs)
        
    elif comparator == "==":
        kwargs_to_pass["minimum_value"] = '"{}"'.format(rhs)
        kwargs_to_pass["maximum_value"] = '"{}"'.format(rhs)

    if feature_name is None:
        feature_name, final_str = gen_feature_name(lhs, comparator, rhs)
    
    return value_set(feature_name, final_str, {k:v for k,v in kwargs_to_pass.items()})


# input_str = [["ANC >= 500" ],["ANC == 200"], ["FiO2 < 0.4"]]
# json_obj = json.loads(json.dumps(input_str))

# out = ''
# for x in json_obj:
#     test = convert_expr_to_value_extraction("""{}""".format(str(x[0])))
#     out += test

# -

def is_numeric(test):
    try:
        int(test)
        float(test)
        return True
    except:
        return False


def cleanup_name(name):
    name = name.strip().lower()
    exclude = set(string.punctuation)
    no_punct_name = ''.join(ch for ch in name if ch not in exclude)
    stop_words = stopwords.words('english')
    stop_words.append('eg')
    stop_words.append('days')
    stop_words.append('date')
    stop_words.append('current')
    stop_words.append('recent')
    stop_words.append('since')
    keys = no_punct_name.lower().split(' ')
    keys = [word for word in keys if word not in stop_words]
    keys = [word for word in keys if len(word) > 1]
    keys = [word for word in keys if not is_numeric(word)]
    if len(keys) > 5:
        keys = keys[0:4]
    clean_name = "_".join(keys).replace('__', '_')
    key_length = len(keys)
    if clean_name.endswith('_'):
        clean_name = clean_name[0:-1]
    return clean_name, key_length



def parse_questions_from_csv(folder_prefix='4100r4',
                             feature_prefix='form_4100_',
                             form_name="Form 4100 R4.0",
                             file_name='/Users/charityhilton/Box/Form4100_analysis_cibmtr.csv'):
    with open(file_name, 'r', encoding='utf-8-sig', errors='ignore') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=',', quotechar='"', dialect='excel')

        form_data = {
            "name": form_name,
            "owner": "gatech",
            "allocated_users": ["admin"],
            "groups": list(),
            "questions": list()
        }

        n = 0

        groups = set()
        group = None
        new_group = False
        termsets = list()
        entities = list()
        operations = list()
        concepts = list()
        results = list()
        comment = ''
        group_number = 1
        evidence_count = 0

        for r in reader:
            row = json.loads(json.dumps(r, indent=4, sort_keys=True).replace('\\u00a0', ' ').replace('\\u00ad', '-')
                             .replace('\\u2265', '>=').replace('\\u2264', '<=').replace('\\u00b3', '3').replace(
                '\\u00b0', ' degrees')
                             .replace('\\u03b3', 'gamma').replace('\\u03b1', 'alpha').replace('\\u00b5', 'u'))
            
            if group and group != row['Group']:
                new_group = True
                
            old_group = group
            
            if not old_group:
                old_group = row['Group']
            question_num = row['Question']
            group = row['Group']
            name = row['Name']
            answers = row['Answers'].split(',')
            codes = row['Code(s)'].split(',')
            code_sys = row['Code System']
            q_type = row['Type']
            terms = row['Terms'].split(',')
            vals = row["Value_Extraction"]
            
            # TODO: extract value extraction arrays of expressions and parse using the helper funcs above; append to NLPQL
            
            # notes = row['Notes (If data present)']

            clean_name, key_length = cleanup_name(name)

            if len(name.strip()) == 0:
                continue

            if q_type == 'MS':
                q_type = 'MULTIPLE_SELECT'
            if q_type == 'MC':
                q_type = 'MULTIPLE_CHOICE'
            if q_type == 'TEXT+MC':
                q_type = 'TEXT_WITH_MULTIPLE_CHOICE'

            answer_sets = list()
            if q_type != 'DATE' and q_type != 'TEXT':
                for a in answers:
                    answer_sets.append({
                        'text': a.replace('\n', ' ').strip(),
                        'value': '_'.join(a.split(' ')).lower().replace('(', '').replace(')', '').replace('.', '')
                            .replace('\n', ' ').strip()
                    })
            group_formatted = '_'.join(old_group.strip().lower().split(' ')).replace(',', '').replace('_/_', '_')
            query_name = 'group_{}_{}'.format(group_number, group_formatted)

            features = list()
            if len(group) > 0:
                groups.add(group)

            comment += '\n\n'
            comment += json.dumps(row, indent=4, sort_keys=True)

            if len(terms) > 0:
                term_string = '", "'.join(terms)
                if term_string.strip() != '':
                    term_string = '"' + term_string + '"'
                    term_string = term_string.replace(', " unspecified",', ',')
                    termsets.append(termset_template.format(str(question_num), clean_name, term_string))
                    pq = '''Clarity.ProviderAssertion({
      termset: [question_%s_%s_terms]
    });
                    ''' % (str(question_num), clean_name)
                    pa = provider_assertion_template.format(question_num, clean_name, pq)
                    features.append('question_{}_{}_assertion'.format(question_num, clean_name))
                    entities.append(pa)
            
            # Inject each value extraction statement to the nlpql 
#             if len(vals)>0:
#                 if len(vals) == 1 and vals[0].strip() == '':
#                     pass
#                 else:
#                     vals_str = ''
#                     for v in vals:
#                         print(v)
#                         val_extraction_stmt = convert_expr_to_value_extraction("""{}""".format(str(v[0])))
#                         vals_str += val_extraction_stmt
                    
            if len(codes) > 0:
                if len(codes) == 1 and codes[0].strip() == '':
                    pass
                else:
                    c_string = ''
                    for c in codes:
                        if len(c_string) > 0:
                            c_string += ', \n    '
                        c_string += 'Code \'{}\' from "{}"'.format(c, code_sys)
                    concepts.append(cql_concept_template % (question_num, clean_name, c_string))
                    resource = 'Observation'
                    if code_sys == 'RxNorm':
                        resource = 'Medication'

                    results.append(cql_result_template.format(question_num, clean_name, resource, question_num, clean_name))
                    features.append('question_{}_{}_coded'.format(question_num, clean_name))
            if new_group:
                with open('/Users/charityhilton/repos/CIBMTR_knowledge_base/{}/group_{}_{}.nlpql'.format(folder_prefix,
                                                                                                         group_number,
                                                                                                         group_formatted),
                          'w') as f:
                    ts_string = '\n\n'.join(termsets)
                    de_string = '\n\n'.join(entities)
                    op_string = '\n\n'.join(operations)
                    query = nlpql_template2.format(form_name, old_group, ts_string, de_string, op_string, comment)
                    f.write(query)
                with open('/Users/charityhilton/repos/CIBMTR_knowledge_base/{}/group_{}_{}.cql'.format(folder_prefix,
                                                                                                       group_number,
                                                                                                       group_formatted),
                          'w') as f:
                    cs_string = '\n\n'.join(concepts)
                    rs_string = '\n\n'.join(results)
                    query = cql_template.format(cs_string, rs_string)
                    f.write(query)
                group_number += 1
                termsets = list()
                entities = list()
                operations = list()
                concepts = list()
                results = list()
                comment = ''
                new_group = False
                # form, group, termsets, data entities, operations, comments

            evidence = dict()
            if len(features) > 0:
                evidence = {
                    query_name: features
                }
                evidence_count += 1
            q = {
                "question_name": name,
                "question_type": q_type,
                "question_number": question_num,
                "group": group,
                "answers": answer_sets,
                "evidence_bundle": evidence
            }
            form_data['questions'].append(q)
            n += 1

        form_data['groups'] = list(groups)
        with open('/Users/charityhilton/repos/CIBMTR_knowledge_base/{}/questions.json'.format(folder_prefix),
                  'w') as f:
            form_data['questions_with_evidence_count'] = evidence_count
            f.write(json.dumps(form_data, indent=4))
        print(evidence_count)
        return form_data


def parse_questions_to_features(
        file_name='/Users/charityhilton/Downloads/CIBMTR - Form 4100 Mapping - QuestionAnalysis.csv'):
    with open(file_name, 'r', encoding='utf-8-sig', errors='ignore') as csvfile:
        reader = csv.DictReader(csvfile, delimiter=',', quotechar='"')

        with open('/Users/charityhilton/Downloads/cibmtr_features.csv', 'w') as csvfile_output:
            writer = csv.writer(csvfile_output)
            writer.writerow(['#', 'question_name', 'answers', 'group', 'question_type', 'evidence_bundle', 'feature_name', 'fhir_resource_type', 'code_system',
                             'codes', 'valueset_oid', 'nlp_task_type', 'text_terms', 'value_min', 'value_max',
                             'value_enum_set', 'logic'])
            for r in reader:
                row = json.loads(json.dumps(r, indent=4, sort_keys=True).replace('\\u00a0', ' ').replace('\\u00ad', '-')
                                 .replace('\\u2265', '>=').replace('\\u2264', '<=').replace('\\u00b3', '3').replace(
                    '\\u00b0', ' degrees')
                                 .replace('\\u03b3', 'gamma').replace('\\u03b1', 'alpha').replace('\\u00b5', 'u'))
                question_num = row['Question'].strip().lower()
                evidence = row['Evidence Bundle'].strip().lower()
                group = row['Group'].strip().lower()
                name = row['Name'].strip().lower()
                answers = row['Answers'].strip().lower()
                codes = row['Codes'].strip()
                oid = row['OID'].strip()
                code_sys = row['Code_System'].strip()
                q_type = row['Type'].strip()
                terms = row['Terms'].strip()
                value_min = row['Value_Min'].strip()
                value_max = row['Value_Max'].strip()
                value_ex = row['Value_Extraction'].strip()
                resource = 'Observation'
                if code_sys == 'RxNorm':
                    resource = 'Medication'

                clean_name, key_length = cleanup_name(name)
                clean_group_name, group_key_length = cleanup_name(group)

                if key_length <= 2:
                    clean_name += ('_' + clean_group_name)

                if len(question_num) > 0:
                    found = False
                    if not evidence or len(evidence) == 0:
                        evidence = clean_name
                    if len(codes) > 0 and q_type != 'DATE':
                        writer.writerow([question_num, name, answers, group, q_type, evidence, clean_name + '_structured', resource, code_sys,
                                         codes, oid, 'CQLTask', '', '', '',
                                         '', ''])
                        found = True

                    if (len(value_min) > 0 or len(value_max) > 0 or len(value_min) > 0 or len(value_ex) > 0) and value_ex \
                            != 'N/A' and q_type != 'DATE':
                        writer.writerow([question_num, name, answers, group, q_type, evidence, clean_name + '_value_extraction', '', '',
                                         '', '', 'ValueExtraction', terms, value_min, value_max,
                                         '', value_ex])
                        found = True
                    elif len(terms) > 0 and q_type != 'DATE':
                        writer.writerow([question_num, name, answers, group, q_type, evidence, clean_name + '_unstructured', '', '',
                                         '', '', 'ProviderAssertion', terms, '', '',
                                         '', ''])
                        found = True

                    if not found:
                        writer.writerow([question_num, name, answers, group, q_type, '', '', '', '',
                                         '', '', '', '', '', ''
                                         '', ''])

                    writer.writerow(['', '', '', '', '', '', '', '', '',
                                         '', '', '', '', '', ''
                                         '', ''])


if __name__ == "__main__":
    import nltk

    nltk.download('stopwords')
    # get_pdfs()
    # form_data = parse_questions()
    # for file in os.listdir("./cimbtr_forms/"):
    #     if file.endswith(".txt"):
    #         stubs(form=file.split('.')[0], form_data=form_data)
    # parse_questions_from_csv()
    parse_questions_to_features()
