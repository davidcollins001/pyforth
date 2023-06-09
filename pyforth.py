# http://git.annexia.org/?p=jonesforth.git;a=blob;f=jonesforth.S
# https://gist.github.com/osa1/66f59158ea99ffefa3658fc6f7c7dd52

import sys

_link = None
_stack_size = 20
_s0 = 0
_r0 = _stack_size
_pad0 = 2 * _stack_size
_dsp = _s0
_rsp = _r0
_pad = _pad0
_dict_start = 3 * _stack_size
_dictionary = _dict_start * [None]
esi = None

_stream = sys.stdin

F_IMMED = 0x80
F_HIDDEN = 0x20
F_LENMASK = 0x1F


def _var_loc(n):
    return _dict_start + 2 * n + 1


_vars = {"LATEST": _var_loc(3),
         "HERE": _var_loc(1),
         "STATE": _var_loc(5),
         "BASE": _var_loc(7),
         "S0": _var_loc(9)}


def _start():
    global esi
    esi = len(_dictionary)
    Interp.quit()


# TODO: move into Interp?
def _load_core(filename=None):
    global _stream
    if not filename:
        filename = ''.join(map(chr, Interp._word()))
    try:
        with open(filename) as f:
            _stream = f
            while True:
                Interp.interpret(f)
    except StopIteration:
        _stream = sys.stdin
        pass


def defcode(name, namelen, code, flags=0):
    global _link
    # link is start of previous entry in _dictionary
    link, _link = _link, len(_dictionary)
    _dictionary.extend([link, flags + namelen, name.upper()])
    if isinstance(code, list):
        _dictionary.extend(code)
    else:
        _dictionary.append(code)
    if len(_dictionary) > _vars["LATEST"]:
        _dictionary[_vars["LATEST"]] = _link
        _dictionary[_vars["HERE"]] = len(_dictionary)


def defword(name, namelen, code, flags=0):
    defcode(name, namelen, [Compiler.docol] + code(), flags)


def defvar(name, namelen, initial=0, flags=0):
    defcode(name, namelen, initial, flags)


def defconst(name, namelen, value, flags=0):
    defword(name, namelen,
            lambda: [Compiler._w2a("LIT"), value, Compiler._w2a("EXIT")],
            flags)


# --- code for builtin forth words ---


class Interp:
    input_buffer = []
    word_buffer = []
    frame = 0
    interpret_is_lit = 0

    @staticmethod
    def exit():
        global esi
        esi = Asm.poprsp()
        Interp.frame -= 1

    @staticmethod
    def _key(stream=sys.stdin):
        if not Interp.input_buffer:
            input_buffer = next(stream)
            Interp.input_buffer = list(map(ord, input_buffer))
            return Interp._key(stream)
        else:
            return Interp.input_buffer.pop(0)

    @staticmethod
    def key():
        value = Interp._key(stream=_stream)
        Asm.push(value)

    @staticmethod
    def _word(stream=sys.stdin):
        Interp.word_buffer = []
        last_key = None
        while True:
            key = Interp._key(stream)
            # TODO: capture \ with space after
            # start of comment in user input
            if key == ord('\\') and (last_key is None or last_key < ord(' ')):
                # ignore everything to end of line
                while key != ord('\n'):
                    key = Interp._key(stream)
            elif key > ord(' '):
                Interp.word_buffer.append(key)
                last_key = key
            else:
                break

        # save push word address and length
        return Interp.word_buffer

    @staticmethod
    def word():
        word = Interp._word()
        Asm.push(word)

    @staticmethod
    def _number(word):
        unparsed = 0
        parsed = 0
        base = _dictionary[_vars["BASE"]]
        neg = 1

        # check for first char being -
        for i, c in enumerate(word):
            try:
                if chr(c) == '-':
                    neg = -1
                else:
                    c = int(chr(c), base)
                    parsed *= base
                    parsed += c
            except ValueError:
                unparsed += 1
        return neg * parsed, unparsed

    @staticmethod
    def number():
        # TODO: is this needed?
        # Interp.word_buffer = [Asm.pop() for _ in range(len_)]
        word = Asm.pop()

        found, errors = Interp._number(word)

        # push parsed numbers and number of unparsed chars
        Asm.push(found)
        Asm.push(errors)

    @staticmethod
    def _find(word):
        word = ''.join(map(chr, word)).upper()
        ndx = _dictionary[_vars["LATEST"]]
        while ndx is not None:
            flags = _dictionary[ndx + 1]
            if word == _dictionary[ndx + 2] and not flags & F_HIDDEN:
                break
            ndx = _dictionary[ndx]
        return ndx

    @staticmethod
    def find():
        word = Asm.pop()
        addr = Interp._find(word)
        if addr:
            Asm.push(addr)

    @staticmethod
    def _tcfa(addr):
        return addr + 3

    @staticmethod
    def tcfa():
        addr = Asm.pop()
        addr = Interp._tcfa(addr)
        Asm.push(addr)

    @staticmethod
    def tdfa():
        return [
            Compiler._w2a(">CFA"),
            Compiler._w2a("1+"),
            Compiler._w2a("EXIT"),
        ]

    @staticmethod
    def interpret_1(word):
        # not in dict or a word, assume it's literal
        Interp.interpret_is_lit = 1
        raw_word = word
        word, errors = Interp._number(raw_word)
        if errors:
            Interp.interpret_6(raw_word)
        elif word is not None:
            return word

    @staticmethod
    def interpret_2(addr):
        state = _dictionary[_vars["STATE"]]
        if state:
            if Interp.interpret_is_lit:
                Compiler._comma(Compiler._w2a("LIT"))
            Compiler._comma(addr)
        else:
            Interp.interpret_4(addr)

    @staticmethod
    def interpret_3():
        pass

    @staticmethod
    def interpret_4(addr):
        if Interp.interpret_is_lit:
            Interp.interpret_5(addr)
        else:
            # execute word
            word = _dictionary[addr]
            if callable(word):
                # pass next instruction address to docol to allow embedded calls
                word(*((addr,) if word == Compiler.docol else ()))
            else:
                # variable name retrieval
                Asm.push(addr)

    @staticmethod
    def interpret_5(literal):
        if literal is not None:
            # push literal on stack
            Asm.push(literal)
        else:
            print(">>>> interp error")

    @staticmethod
    def interpret_6(word):
        global _dsp
        print(f"PARSE ERROR: {''.join(list(map(chr, word)))}")
        _dsp = _s0

    @staticmethod
    def interpret_7():
        # print something?
        pass

    @staticmethod
    def interpret(stream=sys.stdin):
        global esi
        word = Interp._word(stream)
        if word:
            Interp.interpret_is_lit = 0
            addr = Interp._find(word)
            if addr is not None:
                tcfa = Interp._tcfa(addr)
                esi = tcfa
                if _dictionary[addr + 1] & F_IMMED:
                    Interp.interpret_4(tcfa)
                else:
                    Interp.interpret_2(tcfa)
            else:
                addr = Interp.interpret_1(word)
                Interp.interpret_2(addr)

    @staticmethod
    def quit():
        while True:
            try:
                Interp.interpret()
                # Dict.branch(), -8
            except (KeyboardInterrupt, EOFError):
                exit()
            except Exception:
                Interp.frame = 0

    @staticmethod
    def execute():
        addr = Asm.pop()
        Interp.interpret_4(addr)


class Compiler:
    @staticmethod
    def docol(instruction_p=None):
        global esi
        Asm.pushrsp(esi)
        esi = instruction_p or esi
        Interp.frame += 1
        while Interp.frame:
            esi += 1
            addr = _dictionary[esi]
            Interp.interpret_4(addr)

    def _w2a(w):
        # convert word string to address in _dictionary
        word = list(map(ord, w))
        addr = Interp._find(word)
        return Interp._tcfa(addr)

    @staticmethod
    def colon():
        words = [
            Compiler._w2a("CREATE"),              # create the dictionary entry / header
            Compiler._w2a("LIT"), Compiler.docol,
                Compiler._w2a(","),               # append DOCOL  (the codeword).
            Compiler._w2a("LATEST"),
                Compiler._w2a("HIDDEN"),          # make the word hidden
            Compiler._w2a("]"),                   # go into compile mode.
            Compiler._w2a("EXIT"),                # return from the function.
        ]
        return words

    @staticmethod
    def semicolon():
        words = [
            Compiler._w2a("LIT"), Compiler._w2a("EXIT"),
                Compiler._w2a(","),	            # append EXIT (so word will return)
            Compiler._w2a("LATEST"),
                Compiler._w2a("HIDDEN"), 	        # toggle hidden flag -- unhide the word
            Compiler._w2a("["),                   # go back to IMMEDIATE mode.
            Compiler._w2a("EXIT"),                # return from the function.
        ]
        return words

    @staticmethod
    def create():
        name = Interp._word()

        # store latest as link
        _dictionary.append(_dictionary[_vars["LATEST"]])

        # store word header
        _dictionary.extend([len(name), ''.join(map(chr, name)).upper()])

        # update latest/here
        _dictionary[_vars["LATEST"]] = _dictionary[_vars["HERE"]]
        _dictionary[_vars["HERE"]] = len(_dictionary)

    @staticmethod
    def _comma(word):
        # append data to _dictionary and update HERE
        _dictionary.append(word)
        _dictionary[_vars["HERE"]] = len(_dictionary)

    @staticmethod
    def comma():
        word = Asm.pop()
        Compiler._comma(word)

    @staticmethod
    def rbrac():
        _dictionary[_vars["STATE"]] = 1

    @staticmethod
    def lbrac():
        _dictionary[_vars["STATE"]] = 0

    @staticmethod
    def hide():
        return [Compiler._w2a("WORD"), Compiler._w2a("FIND"),
                Compiler._w2a("HIDDEN"), Compiler._w2a("EXIT")]


class Dict:
    @staticmethod
    def immediate():
        latest = _dictionary[_vars["LATEST"]]
        _dictionary[latest + 1] |= F_IMMED

    @staticmethod
    def hidden():
        ndx = Asm.pop()
        _dictionary[_dictionary[ndx] + 1] ^= F_HIDDEN

    @staticmethod
    def tick():
        # because this isn't running on a proper stack machine esi will be this
        # word and doing Asm.lodsl() on it will get the next word in the
        # dictionary and not the next command to run, so use Interp._word() to
        # get the next word if this is being run in the interpreter
        if _dictionary[esi] == Dict.tick:
            name = Interp._word()
            addr = Compiler._w2a(''.join(map(chr, name)))
        else:
            Asm.lodsl()
            addr = _dictionary[esi]
        Asm.push(addr)

    @staticmethod
    def branch():
        global esi
        # if offset was literal, jump  LIT instruction to get offset
        offset = _dictionary[esi + 1]
        offset = 2 if _dictionary[offset] == Dict.lit else 1
        offset = _dictionary[esi + offset] + offset if offset > 0 else 0
        esi += offset

    @staticmethod
    def zbranch():
        # NOTE: docol adds 1 to esi so branching must take that into account
        cond = Asm.pop()
        if cond:
            Asm.lodsl()
            # if offset was literal jump  LIT instruction too
            if _dictionary[_dictionary[esi]] == Dict.lit:
                Asm.lodsl()
        else:
            Dict.branch()

    @staticmethod
    def litstring():
        global esi
        Asm.lodsl()
        # start address of string is after length
        Asm.push(esi + 1)
        length = _dictionary[esi]
        Asm.push(length)
        esi += length

    @staticmethod
    def tell():
        length = Asm.pop()
        addr = Asm.pop()
        for _ in range(length):
            print(chr(_dictionary[addr]), end='')
            addr += 1
            sys.stdout.flush()

    @staticmethod
    def lit():
        # %esi points to the next command, but in this case it points to the next
        # literal 32 bit integer. Store that literal.
        Asm.lodsl()
        Asm.push(_dictionary[esi])

    @staticmethod
    def char():
        name = Interp._word()
        Asm.push(name[0])

    @staticmethod
    def emit():
        char = Asm.pop()
        if char:
            print(chr(char), end='')
            sys.stdout.flush()

    @staticmethod
    def emit_word():
        addr = Asm.pop()
        if addr:
            print(_dictionary[addr + 2], end='')
            sys.stdout.flush()

    @staticmethod
    def words():
        latest = _vars["LATEST"]
        while latest:
            print(_dictionary[latest + 2], end=" ")
            latest = _dictionary[latest]
        print()


class Asm:
    @staticmethod
    def push(reg):
        global _dsp
        _dictionary[_dsp] = reg
        _dsp += 1

    @staticmethod
    def pop():
        global _dsp
        if _dsp > _s0:
            _dsp -= 1
            return _dictionary[_dsp]
        else:
            _dsp = _s0
            print("ERROR: stack underflow")
            raise

    @staticmethod
    def read(ndx):
        try:
            return _dsp[ndx]
        except Exception as e:
            print(f"ERROR: {e}")

    @staticmethod
    def pushrsp(reg):
        global _rsp
        _dictionary[_rsp] = reg
        _rsp += 1

    @staticmethod
    def poprsp():
        global _rsp
        if _rsp > _r0:
            _rsp -= 1
            return _dictionary[_rsp]
        else:
            _rsp = _r0
            print("ERROR: return stack underflow")

    @staticmethod
    def readrsp(ndx):
        try:
            return _rsp[ndx]
        except Exception as e:
            print(f"ERROR: {e}")

    @staticmethod
    def lodsl():
        global esi
        # load %esi into %eax, increment %esi
        prev = esi
        esi += 1
        return prev


class Manipulators:
    @staticmethod
    def drop():
        Asm.pop()

    @staticmethod
    def swap():
        a, b = Asm.pop(), Asm.pop()
        Asm.push(a)
        Asm.push(b)

    @staticmethod
    def dup():
        try:
            Asm.push(_dictionary[_dsp - 1])
        except Exception as e:
            print(f"ERROR: {e}")

    @staticmethod
    def over():
        try:
            Asm.push(_dictionary[_dsp - 2])
        except Exception as e:
            print(f"ERROR: {e}")

    @staticmethod
    def rot():
        a, b, c = Asm.pop(), Asm.pop(), Asm.pop()
        Asm.push(b)
        Asm.push(a)
        Asm.push(c)

    @staticmethod
    def invrot():
        a, b, c = Asm.pop(), Asm.pop(), Asm.pop()
        Asm.push(a)
        Asm.push(c)
        Asm.push(b)

    @staticmethod
    def ddrop():
        Asm.pop()
        Asm.pop()

    @staticmethod
    def dswap():
        a, b, c, d = Asm.pop(), Asm.pop(), Asm.pop(), Asm.pop()
        Asm.push(b)
        Asm.push(a)
        Asm.push(d)
        Asm.push(c)

    @staticmethod
    def ddup():
        try:
            Asm.push(_dictionary[_dsp - 2])
            Asm.push(_dictionary[_dsp - 2])
        except Exception as e:
            print(f"ERROR: {e}")

    @staticmethod
    def qdup():
        d = Asm.pop()
        Asm.push(d)
        if d:
            Asm.push(d)

    @staticmethod
    def onep():
        Asm.push(Asm.pop() + 1)

    @staticmethod
    def onem():
        Asm.push(Asm.pop() - 1)

    @staticmethod
    def twop():
        Asm.push(Asm.pop() + 2)

    @staticmethod
    def twom():
        Asm.push(Asm.pop() - 2)

    @staticmethod
    def plus():
        a, b = Asm.pop(), Asm.pop()
        Asm.push(a + b)

    @staticmethod
    def sub():
        a, b = Asm.pop(), Asm.pop()
        Asm.push(b - a)

    @staticmethod
    def mul():
        a, b = Asm.pop(), Asm.pop()
        Asm.push(a * b)

    @staticmethod
    def divmod():
        a, b = Asm.pop(), Asm.pop()
        [Asm.push(v) for v in reversed(divmod(b, a))]

    @staticmethod
    def equal():
        a, b = Asm.pop(), Asm.pop()
        Asm.push(a == b)

    @staticmethod
    def neq():
        a, b = Asm.pop(), Asm.pop()
        Asm.push(a != b)

    @staticmethod
    def lt():
        b, a = Asm.pop(), Asm.pop()
        Asm.push(a < b)

    @staticmethod
    def gt():
        b, a = Asm.pop(), Asm.pop()
        Asm.push(a > b)

    @staticmethod
    def leq():
        b, a = Asm.pop(), Asm.pop()
        Asm.push(a <= b)

    @staticmethod
    def geq():
        b, a = Asm.pop(), Asm.pop()
        Asm.push(a >= b)

    @staticmethod
    def zeq():
        a = Asm.pop()
        Asm.push(a == 0)

    @staticmethod
    def zneq():
        a = Asm.pop()
        Asm.push(a != 0)

    @staticmethod
    def zlt():
        a = Asm.pop()
        Asm.push(a < 0)

    @staticmethod
    def zleq():
        a = Asm.pop()
        Asm.push(a <= 0)

    @staticmethod
    def zgt():
        a = Asm.pop()
        Asm.push(a > 0)

    @staticmethod
    def zgeq():
        a = Asm.pop()
        Asm.push(a >= 0)

    @staticmethod
    def and_():
        a, b = Asm.pop(), Asm.pop()
        Asm.push(a & b)

    @staticmethod
    def or_():
        a, b = Asm.pop(), Asm.pop()
        Asm.push(a | b)

    @staticmethod
    def xor():
        a, b = Asm.pop(), Asm.pop()
        Asm.push(a ^ b)

    @staticmethod
    def inv():
        Asm.push(-Asm.pop())


class Stack:
    @staticmethod
    def tor():
        Asm.pushrsp(Asm.pop())

    @staticmethod
    def rto():
        Asm.push(Asm.poprsp())

    @staticmethod
    def rspat():
        Asm.push(_rsp)

    @staticmethod
    def rstor():
        global _rsp
        new_rsp = Asm.pop()
        Interp.frame -= (_rsp - new_rsp - 1)
        _rsp = new_rsp

    @staticmethod
    def rdrop():
        Asm.poprsp()

    @staticmethod
    def dspat():
        # mov %esp,%eax
        # push %eax
        Asm.push(_dsp)

    @staticmethod
    def dspstor():
        # pop %esp
        global _dsp
        _dsp = Asm.pop()


class Memory:
    @staticmethod
    def stor():
        addr = Asm.pop()                 # address to store at
        data = Asm.pop()                 # data to store there
        _dictionary[addr] = data         # store it

    @staticmethod
    def fetch():
        addr = Asm.pop()             # address to fetch
        data = _dictionary[addr]     # fetch it
        Asm.push(data)               # push value onto stack

    @staticmethod
    def pstor():
        addr = Asm.pop()             # address
        data = Asm.pop()             # the amount to add
        _dictionary[addr] += data

    @staticmethod
    def mstor():
        addr = Asm.pop()             # address
        data = Asm.pop()             # the amount to add
        _dictionary[addr] -= data

    @staticmethod
    def cstor():
        # pop %ebx                // address to store at
        # pop %eax                // data to store there
        # movb %al,(%ebx)         // store it
        Memory.stor()

    @staticmethod
    def cat():
        # pop %ebx                // address to fetch
        # xor %eax,%eax
        # movb (%ebx),%al         // fetch it
        # push %eax               // push value onto stack
        return Memory.fetch()

    # #(/* C@C! is a useful byte copy primitive. */
    # defcode("C@C!", 4, "
            # movl 4(%esp),%ebx       // source address
            # movb (%ebx),%al         // get source character
            # pop %edi                // destination address
            # stosb                   // copy to destination
            # push %edi               // increment destination address
            # incl 4(%esp)            // increment source address
            # Interp.next")

    @staticmethod
    def cmove():
        # mov %esi,%edx           // preserve %esi
        # pop %ecx                // length
        # pop %edi                // destination address
        # pop %esi                // source address
        # rep movsb               // copy source to destination
        # mov %edx,%esi           // restore %esi
        pass


# --- VARIABLES ---
# hard coded to point to end of _dictionary
defvar("HERE", 4, 0)
defvar("LATEST", 6, 0)
defvar("STATE", 5, 0)
defvar("BASE", 4, 10)
defvar("S0", 2, _s0)


# --- MANIPULATORS ---
defcode("DROP", 4, Manipulators.drop)
defcode("SWAP", 4, Manipulators.swap)
defcode("DUP", 3, Manipulators.dup)
defcode("OVER", 4, Manipulators.over)
defcode("ROT", 3, Manipulators.rot)
defcode("-ROT", 4, Manipulators.invrot)
defcode("2DUP", 4, Manipulators.ddup)
defcode("2DROP", 5, Manipulators.ddrop)
defcode("2SWAP", 5, Manipulators.dswap)
defcode("?DUP", 4, Manipulators.qdup)
defcode("1+", 2, Manipulators.onep)
defcode("1-", 2, Manipulators.onem)
defcode("2+", 2, Manipulators.twop)
defcode("2-", 2, Manipulators.twom)
# defcode("4+", 2, "
        # addl $4,(%esp)          // add 4 to top of stack
        # Interp.NEXT")
# defcode("4-", 2, "
        # subl $4,(%esp)          // subtract 4 from top of stack
        # Interp.NEXT")
defcode("+", 1, Manipulators.plus)
defcode("-", 1, Manipulators.sub)
defcode("*", 1, Manipulators.mul)
defcode("/MOD", 4, Manipulators.divmod)
defcode("=", 1, Manipulators.equal)
defcode("<>", 2, Manipulators.neq)
defcode("<", 1, Manipulators.lt)
defcode(">", 1, Manipulators.gt)
defcode("<=", 2, Manipulators.leq)
defcode(">=", 2, Manipulators.geq)
defcode("0=", 2, Manipulators.zeq)
defcode("0<>", 3, Manipulators.zneq)
defcode("0<", 2, Manipulators.zlt)
defcode("0>", 2, Manipulators.zgt)
defcode("0<=", 3, Manipulators.zleq)
defcode("0>=", 3, Manipulators.zgeq)
defcode("AND", 3, Manipulators.and_)
defcode("OR", 2, Manipulators.or_)
defcode("XOR", 3, Manipulators.xor)
defcode("INVERT", 6, Manipulators.inv)


# --- MEMORY ---
defcode("!", 1, Memory.stor)
defcode("@", 5, Memory.fetch)
defcode("+!", 2, Memory.pstor)
defcode("-!", 2, Memory.mstor)
defcode("C!", 2, Memory.cstor)
defcode("C@", 2, Memory.cat)
# c@c! is a useful byte copy primitive.
# defcode("C@C!", 4, MEMORY.)
# and CMOVE is a block copy operation.
defcode("CMOVE", 5, Memory.cmove)


# --- DICT ---
defcode("LIT", 3, Dict.lit)
defcode("EMIT", 4, Dict.emit)
defcode("ID.", 3, Dict.emit_word)
defcode("WORDS", 5, Dict.words)
defcode("IMMEDIATE", 9, Dict.immediate, flags=F_IMMED)
defcode("HIDDEN", 6, Dict.hidden)
defcode("BRANCH", 6, Dict.branch)
defcode("0BRANCH", 7, Dict.zbranch)
defcode("LITSTRING", 9, Dict.litstring)
defcode("TELL", 4, Dict.tell)
defcode("CHAR", 4, Dict.char)
defcode("'", 1, Dict.tick)
defcode("INCLUDE", 7, _load_core)


# --- INTERPRETER ---
defcode("EXIT", 4, Interp.exit)
defcode("KEY", 3, Interp.key)
defcode("WORD", 4, Interp.word)
defcode("FIND", 4, Interp.find)
defcode(">CFA", 4, Interp.tcfa)
defword(">DFA", 4, Interp.tdfa)
defcode("CREATE", 6, Compiler.create)
defcode(",", 1, Compiler.comma)
defcode("[", 1, Compiler.lbrac, flags=F_IMMED)
defcode("]", 1, Compiler.rbrac)
defcode("EXECUTE", 7, Interp.execute)
defcode("QUIT", 4, Interp.quit)
defcode("INTERPRET", 9, Interp.interpret)
defword("HIDE", 4, Compiler.hide)
defword(":", 1, Compiler.colon)
defword(";", 1, Compiler.semicolon, flags=F_IMMED)
defcode("INCLUDE", 7, _load_core)


# --- STACK ---
defcode(">R", 2, Stack.tor)
defcode("R>", 2, Stack.rto)
defcode("RSP@", 4, Stack.rspat)
defcode("RSP!", 4, Stack.rstor)
defcode("RDROP", 5, Stack.rdrop)
defcode("DSP@", 4, Stack.dspat)
defcode("DSP!", 4, Stack.dspstor)


# --- CONSTANTS ---
defconst("VERSION", 7, "JONES_VERSION")
defconst("R0", 2, _r0)
defconst("PAD", 5, _pad0)
defconst("DOCOL", 5, Compiler.docol)
defconst("F_IMMED", 7, F_IMMED)
defconst("F_HIDDEN", 8, F_HIDDEN)
defconst("F_LENMASK", 9, F_LENMASK)


# defconst("SYS_EXIT", 8, "__NR_exit")
# defconst("SYS_OPEN", 8, "__NR_open")
# defconst("SYS_CLOSE", 9, "__NR_close")
# defconst("SYS_READ", 8, "__NR_read")
# defconst("SYS_WRITE", 9, "__NR_write")
# defconst("SYS_CREAT", 9, "__NR_creat")
# defconst("SYS_BRK", 7, "__NR_brk")

# defconst("O_RDONLY", 8, 0)
# defconst("O_WRONLY", 8, 1)
# defconst("O_RDWR", 6, 2)
# defconst("O_CREAT", 7, 0x0100)
# defconst("O_EXCL", 6, 0x0200)
# defconst("O_TRUNC", 7, 0x01000)
# defconst("O_APPEND", 8, 0x02000)
# defconst("O_NONBLOCK", 10, 0x04000)


# --- TESTING---


defcode(".DS", 2, lambda: print(_dictionary[_s0: _dsp]))
defcode(".RS", 2, lambda: print(_dictionary[_r0: _rsp]))
defcode(".dict", 5, lambda: print(_dictionary))


_load_core("core.fs")
if len(sys.argv) == 1:
    _start()
else:
    for filename in sys.argv[1:]:
        _load_core(filename)
