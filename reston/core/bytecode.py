from __future__ import print_function
from __future__ import absolute_import

from builtins import str
from builtins import range
from builtins import object
import hashlib
from xml.sax.saxutils import escape
from struct import unpack, pack
import textwrap

import json
from .anconf import warning, error, CONF, enable_colors, remove_colors, save_colors, color_range


def disable_print_colors():
    colors = save_colors()
    remove_colors()
    return colors


def enable_print_colors(colors):
    enable_colors(colors)


# Handle exit message
def Exit(msg):
    warning("Error : " + msg)
    raise ("oops")


def Warning(msg):
    warning(msg)


def _PrintBanner():
    print_fct = CONF["PRINT_FCT"]
    print_fct("*" * 75 + "\n")


def _PrintSubBanner(title=None):
    print_fct = CONF["PRINT_FCT"]
    if title == None:
        print_fct("#" * 20 + "\n")
    else:
        print_fct("#" * 10 + " " + title + "\n")


def _PrintNote(note, tab=0):
    print_fct = CONF["PRINT_FCT"]
    note_color = CONF["COLORS"]["NOTE"]
    normal_color = CONF["COLORS"]["NORMAL"]
    print_fct("\t" * tab + "%s# %s%s" % (note_color, note, normal_color) + "\n")


# Print arg into a correct format
def _Print(name, arg):
    buff = name + " "

    if type(arg).__name__ == 'int':
        buff += "0x%x" % arg
    elif type(arg).__name__ == 'long':
        buff += "0x%x" % arg
    elif type(arg).__name__ == 'str':
        buff += "%s" % arg
    elif isinstance(arg, SV):
        buff += "0x%x" % arg.get_value()
    elif isinstance(arg, SVs):
        buff += arg.get_value().__str__()

    print(buff)


def PrettyShowEx(exceptions):
    if len(exceptions) > 0:
        CONF["PRINT_FCT"]("Exceptions:\n")
        for i in exceptions:
            CONF["PRINT_FCT"]("\t%s%s%s\n" %
                              (CONF["COLORS"]["EXCEPTION"], i.show_buff(),
                               CONF["COLORS"]["NORMAL"]))


def _PrintXRef(tag, items):
    print_fct = CONF["PRINT_FCT"]
    for i in items:
        print_fct("%s: %s %s %s %s\n" %
                  (tag, i[0].get_class_name(), i[0].get_name(),
                   i[0].get_descriptor(), ' '.join("%x" % j.get_idx()
                                                   for j in i[1])))


def _PrintDRef(tag, items):
    print_fct = CONF["PRINT_FCT"]
    for i in items:
        print_fct("%s: %s %s %s %s\n" %
                  (tag, i[0].get_class_name(), i[0].get_name(),
                   i[0].get_descriptor(), ' '.join("%x" % j for j in i[1])))


def _PrintDefault(msg):
    print_fct = CONF["PRINT_FCT"]
    print_fct(msg)


def PrettyShow(m_a, basic_blocks, notes={}):
    idx = 0
    nb = 0

    offset_color = CONF["COLORS"]["OFFSET"]
    offset_addr_color = CONF["COLORS"]["OFFSET_ADDR"]
    instruction_name_color = CONF["COLORS"]["INSTRUCTION_NAME"]
    branch_false_color = CONF["COLORS"]["BRANCH_FALSE"]
    branch_true_color = CONF["COLORS"]["BRANCH_TRUE"]
    branch_color = CONF["COLORS"]["BRANCH"]
    exception_color = CONF["COLORS"]["EXCEPTION"]
    bb_color = CONF["COLORS"]["BB"]
    normal_color = CONF["COLORS"]["NORMAL"]
    print_fct = CONF["PRINT_FCT"]

    colors = CONF["COLORS"]["OUTPUT"]

    for i in basic_blocks:
        print_fct("%s%s%s : \n" % (bb_color, i.get_name(), normal_color))
        instructions = i.get_instructions()
        for ins in instructions:
            if nb in notes:
                for note in notes[nb]:
                    _PrintNote(note, 1)

            print_fct("\t%s%-3d%s(%s%08x%s) " %
                      (offset_color, nb, normal_color, offset_addr_color, idx,
                       normal_color))
            print_fct("%s%-20s%s" %
                      (instruction_name_color, ins.get_name(), normal_color))

            operands = ins.get_operands()
            print_fct(
                "%s" %
                ", ".join(m_a.get_vm().colorize_operands(operands, colors)))

            op_value = ins.get_op_value()
            if ins == instructions[-1] and i.childs:
                print_fct(" ")

                # packed/sparse-switch
                if (op_value == 0x2b or op_value == 0x2c) and len(i.childs) > 1:
                    values = i.get_special_ins(idx).get_values()
                    print_fct("%s[ D:%s%s " %
                              (branch_false_color, i.childs[0][2].get_name(),
                               branch_color))
                    print_fct(' '.join("%d:%s" % (
                        values[j], i.childs[j + 1][2].get_name()) for j in
                                       range(0, len(i.childs) - 1)) + " ]%s" %
                              normal_color)
                else:
                    if len(i.childs) == 2:
                        print_fct("%s[ %s%s " % (branch_false_color,
                                                 i.childs[0][2].get_name(),
                                                 branch_true_color))
                        print_fct(' '.join("%s" % c[2].get_name(
                        ) for c in i.childs[1:]) + " ]%s" % normal_color)
                    else:
                        print_fct("%s[ " % branch_color + ' '.join(
                            "%s" % c[2].get_name() for c in i.childs) + " ]%s" %
                                  normal_color)

            idx += ins.get_length()
            nb += 1

            print_fct("\n")

        if i.get_exception_analysis():
            print_fct("\t%s%s%s\n" %
                      (exception_color, i.exception_analysis.show_buff(),
                       normal_color))

        print_fct("\n")


class TmpBlock(object):

    def __init__(self, name):
        self.name = name

    def get_name(self):
        return self.name


def method2json(mx, directed_graph=False):
    if directed_graph:
        return method2json_direct(mx)
    return method2json_undirect(mx)


def method2json_undirect(mx):
    d = {}
    reports = []
    d["reports"] = reports

    for DVMBasicMethodBlock in mx.basic_blocks.gets():
        cblock = {}

        cblock["BasicBlockId"] = DVMBasicMethodBlock.get_name()
        cblock["registers"] = mx.get_method().get_code().get_registers_size()
        cblock["instructions"] = []

        ins_idx = DVMBasicMethodBlock.start
        for DVMBasicMethodBlockInstruction in DVMBasicMethodBlock.get_instructions(
        ):
            c_ins = {}
            c_ins["idx"] = ins_idx
            c_ins["name"] = DVMBasicMethodBlockInstruction.get_name()
            c_ins["operands"] = DVMBasicMethodBlockInstruction.get_operands(
                ins_idx)

            cblock["instructions"].append(c_ins)
            ins_idx += DVMBasicMethodBlockInstruction.get_length()

        cblock["Edge"] = []
        for DVMBasicMethodBlockChild in DVMBasicMethodBlock.childs:
            cblock["Edge"].append(DVMBasicMethodBlockChild[-1].get_name())

        reports.append(cblock)

    return json.dumps(d)


def method2json_direct(mx):
    d = {}
    reports = []
    d["reports"] = reports

    hooks = {}

    l = []
    for DVMBasicMethodBlock in mx.basic_blocks.gets():
        for index, DVMBasicMethodBlockChild in enumerate(
            DVMBasicMethodBlock.childs):
            if DVMBasicMethodBlock.get_name(
            ) == DVMBasicMethodBlockChild[-1].get_name():

                preblock = TmpBlock(DVMBasicMethodBlock.get_name() + "-pre")

                cnblock = {}
                cnblock["BasicBlockId"] = DVMBasicMethodBlock.get_name(
                ) + "-pre"
                cnblock["start"] = DVMBasicMethodBlock.start
                cnblock["notes"] = []

                cnblock["Edge"] = [DVMBasicMethodBlock.get_name()]
                cnblock["registers"] = 0
                cnblock["instructions"] = []
                cnblock["info_bb"] = 0

                l.append(cnblock)

                for parent in DVMBasicMethodBlock.fathers:
                    hooks[parent[-1].get_name()] = []
                    hooks[parent[-1].get_name()].append(preblock)

                    for idx, child in enumerate(parent[-1].childs):
                        if child[-1].get_name() == DVMBasicMethodBlock.get_name(
                        ):
                            hooks[parent[-1].get_name()].append(child[-1])

    for DVMBasicMethodBlock in mx.basic_blocks.gets():
        cblock = {}

        cblock["BasicBlockId"] = DVMBasicMethodBlock.get_name()
        cblock["start"] = DVMBasicMethodBlock.start
        cblock["notes"] = DVMBasicMethodBlock.get_notes()

        cblock["registers"] = mx.get_method().get_code().get_registers_size()
        cblock["instructions"] = []

        ins_idx = DVMBasicMethodBlock.start
        last_instru = None
        for DVMBasicMethodBlockInstruction in DVMBasicMethodBlock.get_instructions(
        ):
            c_ins = {}
            c_ins["idx"] = ins_idx
            c_ins["name"] = DVMBasicMethodBlockInstruction.get_name()
            c_ins["operands"] = DVMBasicMethodBlockInstruction.get_operands(
                ins_idx)

            c_ins["formatted_operands"
                 ] = DVMBasicMethodBlockInstruction.get_formatted_operands()

            cblock["instructions"].append(c_ins)

            if (DVMBasicMethodBlockInstruction.get_op_value() == 0x2b or
                DVMBasicMethodBlockInstruction.get_op_value() == 0x2c):
                values = DVMBasicMethodBlock.get_special_ins(ins_idx)
                cblock["info_next"] = values.get_values()

            ins_idx += DVMBasicMethodBlockInstruction.get_length()
            last_instru = DVMBasicMethodBlockInstruction

        cblock["info_bb"] = 0
        if DVMBasicMethodBlock.childs:
            if len(DVMBasicMethodBlock.childs) > 1:
                cblock["info_bb"] = 1

            if (last_instru.get_op_value() == 0x2b or
                last_instru.get_op_value() == 0x2c):
                cblock["info_bb"] = 2

        cblock["Edge"] = []
        for DVMBasicMethodBlockChild in DVMBasicMethodBlock.childs:
            ok = False
            if DVMBasicMethodBlock.get_name() in hooks:
                if DVMBasicMethodBlockChild[-1] in hooks[
                    DVMBasicMethodBlock.get_name()
                ]:
                    ok = True
                    cblock["Edge"].append(hooks[DVMBasicMethodBlock.get_name(
                    )][0].get_name())

            if not ok:
                cblock["Edge"].append(DVMBasicMethodBlockChild[-1].get_name())

        exception_analysis = DVMBasicMethodBlock.get_exception_analysis()
        if exception_analysis:
            cblock["Exceptions"] = exception_analysis.get()

        reports.append(cblock)

    reports.extend(l)

    return json.dumps(d)


class SV(object):

    def __init__(self, size, buff):
        self.__size = size
        self.__value = unpack(self.__size, buff)[0]

    def _get(self):
        return pack(self.__size, self.__value)

    def __str__(self):
        return "0x%x" % self.__value

    def __int__(self):
        return self.__value

    def get_value_buff(self):
        return self._get()

    def get_value(self):
        return self.__value

    def set_value(self, attr):
        self.__value = attr


class SVs(object):

    def __init__(self, size, ntuple, buff):
        self.__size = size

        self.__value = ntuple._make(unpack(self.__size, buff))

    def _get(self):
        l = []
        for i in self.__value._fields:
            l.append(getattr(self.__value, i))
        return pack(self.__size, *l)

    def _export(self):
        return [x for x in self.__value._fields]

    def get_value_buff(self):
        return self._get()

    def get_value(self):
        return self.__value

    def set_value(self, attr):
        self.__value = self.__value._replace(**attr)

    def __str__(self):
        return self.__value.__str__()


def object_to_bytes(obj):
    """
    Convert a object to a bytearray or call get_raw() of the object
    if no useful type was found.
    """
    if isinstance(obj, str):
        return bytearray(obj, "UTF-8")
    elif isinstance(obj, bool):
        return bytearray()
    elif isinstance(obj, int):
        return pack("<L", obj)
    elif obj == None:
        return bytearray()
    elif isinstance(obj, bytearray):
        return obj
    else:
        #print type(obj), obj
        return obj.get_raw()


class MethodBC(object):

    def show(self, value):
        getattr(self, "show_" + value)()


class BuffHandle(object):

    def __init__(self, buff):
        self.__buff = bytearray(buff)
        self.__idx = 0

    def size(self):
        return len(self.__buff)

    def set_idx(self, idx):
        self.__idx = idx

    def get_idx(self):
        return self.__idx

    def readNullString(self, size):
        data = self.read(size)
        return data

    def read_b(self, size):
        return self.__buff[self.__idx:self.__idx + size]

    def read_at(self, offset, size):
        return self.__buff[offset:offset + size]

    def read(self, size):
        if isinstance(size, SV):
            size = size.value

        buff = self.__buff[self.__idx:self.__idx + size]
        self.__idx += size

        return buff

    def end(self):
        return self.__idx == len(self.__buff)


class Buff(object):

    def __init__(self, offset, buff):
        self.offset = offset
        self.buff = buff

        self.size = len(buff)


class _Bytecode(object):

    def __init__(self, buff):
        self.__buff = bytearray(buff)
        self.__idx = 0

    def read(self, size):
        if isinstance(size, SV):
            size = size.value

        buff = self.__buff[self.__idx:self.__idx + size]
        self.__idx += size

        return buff

    def readat(self, off):
        if isinstance(off, SV):
            off = off.value

        return self.__buff[off:]

    def read_b(self, size):
        return self.__buff[self.__idx:self.__idx + size]

    def set_idx(self, idx):
        self.__idx = idx

    def get_idx(self):
        return self.__idx

    def add_idx(self, idx):
        self.__idx += idx

    def register(self, type_register, fct):
        self.__registers[type_register].append(fct)

    def get_buff(self):
        return self.__buff

    def length_buff(self):
        return len(self.__buff)

    def set_buff(self, buff):
        self.__buff = buff

    def save(self, filename):
        buff = self._save()
        with open(filename, "wb") as fd:
            fd.write(buff)


def FormatClassToJava(input):
    """
       Transoform a typical xml format class into java format

       :param input: the input class name
       :rtype: string
    """
    return "L" + input.replace(".", "/") + ";"


def FormatClassToPython(input):
    i = input[:-1]
    i = i.replace("/", "_")
    i = i.replace("$", "_")

    return i


def FormatNameToPython(input):
    i = input.replace("<", "")
    i = i.replace(">", "")
    i = i.replace("$", "_")

    return i


def FormatDescriptorToPython(input):
    i = input.replace("/", "_")
    i = i.replace(";", "")
    i = i.replace("[", "")
    i = i.replace("(", "")
    i = i.replace(")", "")
    i = i.replace(" ", "")
    i = i.replace("$", "")

    return i


class Node(object):

    def __init__(self, n, s):
        self.id = n
        self.title = s
        self.children = []