# http://git.annexia.org/?p=jonesforth.git;a=blob;f=jonesforth.S
# https://gist.github.com/osa1/66f59158ea99ffefa3658fc6f7c7dd52

import sys

_data_stack = []
_return_stack = []
_dictionary = []

_vars = {"LATEST": 7, "HERE": 3, "STATE": 11, "BASE": 19}
_link = None

esi = 0

F_IMMED = 0x80
F_HIDDEN = 0x20
F_LENMASK = 0x1f


def _start():
    global esi
    esi = 0
    Interp.quit()


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
    defcode(name, namelen, [Interp.docol] + code(), flags)


def defvar(name, namelen, initial=0, flags=0):
    defcode(name, namelen, initial, flags)


def defconst(name, namelen, value, flags=0):
    defword(name, namelen,
            lambda: [Interp._w2a("LIT"), value, Interp._w2a("EXIT")],
            flags)


# --- code for builtin forth words ---


class Interp:
    input_buffer = []
    word_buffer = []
    docol_run = 0
    interpret_is_lit = 0

    @staticmethod
    def docol(instruction_p=None):
        global esi
        Asm.pushrsp(esi)
        esi = instruction_p or esi
        Interp.docol_run += 1
        while Interp.docol_run:
            esi += 1
            addr = _dictionary[esi]
            Interp.interpret_4(addr)

    @staticmethod
    def exit():
        global esi
        esi = Asm.poprsp()
        Interp.docol_run -= 1

    @staticmethod
    def lit():
        # %esi points to the next command, but in this case it points to the next
        # literal 32 bit integer. Store that literal.
        Asm.lodsl()
        Asm.push(_dictionary[esi])

    @staticmethod
    def _key():
        if not Interp.input_buffer:
            input_buffer = sys.stdin.readline()
            if input_buffer == '':
                exit()
            Interp.input_buffer = list(map(ord, input_buffer))
            return Interp._key()
        else:
            return Interp.input_buffer.pop(0)

    @staticmethod
    def key():
        value = Interp._key()
        Asm.push(value)

    @staticmethod
    def emit():
        char = Asm.pop()
        if char:
            print(chr(char), end="")

    @staticmethod
    def _word():
        Interp.word_buffer = []
        last_key = None
        while True:
            key = Interp._key()
            # TODO: capture \ with space after
            # start of comment in user input
            if key == ord('\\') and (last_key is None or last_key < ord(' ')):
                # ignore everything to end of line
                while key != ord('\n'):
                    key = Interp._key()
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
            Interp._w2a(">CFA"),
            Interp._w2a("1+"),
            Interp._w2a("EXIT"),
        ]

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
        Interp._comma(word)

    @staticmethod
    def rbrac():
        _dictionary[_vars["STATE"]] = 1

    @staticmethod
    def lbrac():
        _dictionary[_vars["STATE"]] = 0

    def _w2a(w):
        # convert word string to address in _dictionary
        word = list(map(ord, w))
        addr = Interp._find(word)
        return Interp._tcfa(addr)

    @staticmethod
    def colon():
        words = [
            Interp._w2a("CREATE"),              # create the dictionary entry / header
            Interp._w2a("LIT"), Interp.docol,
                Interp._w2a(","),               # append DOCOL  (the codeword).
            Interp._w2a("LATEST"),
                Interp._w2a("HIDDEN"),          # make the word hidden
            Interp._w2a("]"),                   # go into compile mode.
            Interp._w2a("EXIT"),                # return from the function.
        ]
        return words

    @staticmethod
    def semicolon():
        words = [
            Interp._w2a("LIT"), Interp._w2a("EXIT"),
                Interp._w2a(","),	            # append EXIT (so word will return)
            Interp._w2a("LATEST"),
                Interp._w2a("HIDDEN"), 	        # toggle hidden flag -- unhide the word
            Interp._w2a("["),                   # go back to IMMEDIATE mode.
            Interp._w2a("EXIT"),                # return from the function.
        ]
        return words

    @staticmethod
    def immediate():
        latest = _dictionary[_vars["LATEST"]]
        _dictionary[latest + 1] |= F_IMMED

    @staticmethod
    def hidden():
        ndx = Asm.pop()
        _dictionary[_dictionary[ndx] + 1] ^= F_HIDDEN

    @staticmethod
    def hide():
        return [Interp._w2a("WORD"), Interp._w2a("FIND"),
                Interp._w2a("HIDDEN"), Interp._w2a("EXIT")]

    @staticmethod
    def tick():
        # because this isn't running on a proper stack machine esi will be this
        # word and doing Asm.lodsl() on it will get the next word in the
        # dictionary and not the next command to run, so use Interp._word() to
        # get the next word if this is being run in the interpreter
        if _dictionary[esi] == Interp.tick:
            name = Interp._word()
            addr = Interp._w2a(''.join(map(chr, name)))
        else:
            Asm.lodsl()
            addr = _dictionary[esi]
        Asm.push(addr)

    @staticmethod
    def branch():
        global esi
        # if offset was literal jump  LIT instruction to get offset
        offset = _dictionary[esi + 1]
        offset = 2 if _dictionary[offset] == Interp.lit else 1
        offset = _dictionary[esi + offset] + offset
        esi += offset

    @staticmethod
    def zbranch():
        # NOTE: docol adds 1 to esi so branching must take that into account
        cond = Asm.pop()
        if cond:
            Asm.lodsl()
            Asm.lodsl()
        else:
            Interp.branch()

    @staticmethod
    def litstring():
        global esi
        # TODO: implement
        # lodsl                   // get the length of the string
        Asm.lodsl()
        # push %esi               // push the address of the start of the string
        # push %eax               // push it on the stack
        # addl %eax,%esi          // skip past the string
        # addl $3,%esi            // but round up to next 4 byte boundary
        # andl $~3,%esi
        Asm.push(_dictionary[esi])
        # TODO: get length
        length = 1
        Asm.push(length)
        esi += length

    @staticmethod
    def tell():
        Asm.pop()  # length
        word = Asm.pop()
        print(''.join(map(chr, word)))

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
                Interp._comma(Interp._w2a("LIT"))
            Interp._comma(addr)
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
                word(*((addr,) if word == Interp.docol else ()))
            else:
                # variable name retrieval
                Asm.push(addr)

    @staticmethod
    def interpret_5(literal):
        if literal is not None:
            # push literal on stack
            Asm.push(literal)
        else:
            import pdb; pdb.set_trace()  # noqa

    @staticmethod
    def interpret_6(word):
        global _data_stack
        print(f"PARSE ERROR: {''.join(list(map(chr, word)))}")
        _data_stack = []

    @staticmethod
    def interpret_7():
        # print something?
        pass

    @staticmethod
    def interpret():
        global esi
        word = Interp._word()
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
            Interp.interpret()
            # Interp.branch(), -8

    @staticmethod
    def char():
        name = Interp._word()
        Asm.push(name[0])

    @staticmethod
    def execute():
        addr = Asm.pop()
        Interp.interpret_4(addr)


class Asm:
    @staticmethod
    def push(reg):
        _data_stack.append(reg)

    @staticmethod
    def pop():
        try:
            return _data_stack.pop()
        except Exception as e:
            print(f"ERROR: {e}")

    @staticmethod
    def read(ndx):
        try:
            return _data_stack[ndx]
        except Exception as e:
            print(f"ERROR: {e}")

    @staticmethod
    def pushrsp(reg):
        _return_stack.append(reg)

    @staticmethod
    def poprsp():
        try:
            return _return_stack.pop()
        except Exception as e:
            print(f"ERROR: {e}")

    @staticmethod
    def readrsp(ndx):
        try:
            return _return_stack[ndx]
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
            Asm.push(_data_stack[-1])
        except Exception as e:
            print(f"ERROR: {e}")

    @staticmethod
    def over():
        try:
            Asm.push(_data_stack[-2])
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
            _data_stack.extend(_data_stack[-2:])
        except Exception as e:
            print(f"ERROR: {e}")

    @staticmethod
    def qdup():
        d = Asm.pop()
        if d:
            Asm.push(d)
            Asm.push(d)

    @staticmethod
    def onep():
        Asm.push(Asm.pop() + 1)

    @staticmethod
    def onem():
        Asm.push(Asm.pop() - 1)

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
        [Asm.push(v) for v in divmod(a, b)]

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
        Asm.PUSh(a != 0)

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
        Asm.pushrsp(Asm.pop())

    @staticmethod
    def rspat():
        Asm.push(Asm.readrsp(-1))

    @staticmethod
    def rstor():
        Asm.pushrsp(Asm.pop())

    @staticmethod
    def rdrop():
        Asm.poprsp()

    @staticmethod
    def dspat():
        # mov %esp,%eax
        # push %eax
        print("TODO: DSPAT")

    @staticmethod
    def dspstor():
        # pop %esp
        print("TODO: DSPAT")


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
        pass

    @staticmethod
    def cat():
        # pop %ebx                // address to fetch
        # xor %eax,%eax
        # movb (%ebx),%al         // fetch it
        # push %eax               // push value onto stack
        pass

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
defvar("S0", 2, 0)
defvar("BASE", 4, 10)


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


# --- INTERPRETER ---
defcode("EXIT", 4, Interp.exit)
defcode("LIT", 3, Interp.lit)
defcode("KEY", 3, Interp.key)
defcode("WORD", 4, Interp.word)
defcode("EMIT", 4, Interp.emit)
defcode("FIND", 4, Interp.find)
defcode(">CFA", 4, Interp.tcfa)
defword(">DFA", 4, Interp.tdfa)
defcode("CREATE", 6, Interp.create)
defcode(",", 1, Interp.comma)
defcode("[", 1, Interp.lbrac, flags=F_IMMED)
defcode("]", 1, Interp.rbrac)
defcode("IMMEDIATE", 9, Interp.immediate, flags=F_IMMED)
defcode("HIDDEN", 6, Interp.hidden)
defcode("BRANCH", 6, Interp.branch)
defcode("0BRANCH", 7, Interp.zbranch)
defcode("LITSTRING", 9, Interp.litstring)
defcode("TELL", 4, Interp.tell)
defcode("InterpRET", 9, Interp.interpret)
defcode("CHAR", 4, Interp.char)
defcode("EXECUTE", 7, Interp.execute)
defword("HIDE", 4, Interp.hide)
defcode("'", 1, Interp.tick)
defword(":", 1, Interp.colon)
defword(";", 1, Interp.semicolon, flags=F_IMMED)


# --- STACK ---
defcode(">R", 2, Stack.tor)
defcode("R>", 2, Stack.rto)
defcode("R@", 4, Stack.rspat)
defcode("R!", 4, Stack.rstor)
defcode("RDROP", 5, Stack.rdrop)
defcode("DSP@", 4, Stack.dspat)
defcode("DSP!", 4, Stack.dspstor)


# --- CONSTANTS ---
defconst("VERSION", 7, "JONES_VERSION")
defconst("R0", 2, 0)
defconst("DOCOL", 5, Interp.docol)
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


defcode(".S", 2, lambda: print(_data_stack))
defcode(".R", 2, lambda: print(_return_stack))
defcode(".dict", 5, lambda: print(_dictionary))

_start()
