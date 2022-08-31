import sys

_data_stack = []
_return_stack = []
_dictionary = []

_vars = {"LATEST": None, "HERE": 0, "STATE": 0, "BASE": 10}
_const = {}

esi = 0

F_IMMED = 0x80
F_HIDDEN = 0x20
F_LENMASK = 0x1f


def _start():
    global esi
    esi = 0
    Interp.quit()


def defword(name, namelen, code, flags=0):
    # link is start of previous entry in _dictionary
    link, _vars["LATEST"] = _vars["LATEST"], _vars["HERE"]
    _dictionary.extend([link, flags + namelen, name.upper(), Interp.docol])
    # add number of commands and commands to run to _dictionary
    _dictionary.extend(code())
    _vars["HERE"] = len(_dictionary)


def defcode(name, namelen, code, flags=0):
    # link is start of previous entry in _dictionary
    link, _vars["LATEST"] = _vars["LATEST"], _vars["HERE"]
    _dictionary.extend([link, flags + namelen, name.upper()])
    _dictionary.append(code)
    _vars["HERE"] = len(_dictionary)


def defvar(name, namelen, initial=0, flags=0):
    defcode(name, namelen, initial, flags)
    # push $var_\name
    # Asm.push(_vars['HERE'] - 1)
    # _vars[name.upper()] = initial


def defconst(name, namelen, value, flags=0):
    defcode(name, namelen, value, flags)
    # push $\value
    _const[name.upper()] = value


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
            word = _dictionary[addr]
            word(*((addr,) if word == Interp.docol else ()))

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
            Interp.input_buffer = list(map(ord, sys.stdin.readline()))
            return Interp._key()
        else:
            return Interp.input_buffer.pop(0)

    @staticmethod
    def key():
        value = Interp._key()
        Asm.push(value)

    @staticmethod
    def emit():
        print(chr(Asm.pop()), end="")

    @staticmethod
    def _word():
        Interp.word_buffer = []
        while True:
            key = Interp._key()
            # start of comment
            if key == ord('\\'):
                # ignore everything to end of line
                while key != ord('\n'):
                    key = Interp._key()
            elif key > ord(' '):
                Interp.word_buffer.append(key)
            else:
                break

        # save push word address and length
        return len(Interp.word_buffer), Interp.word_buffer

    @staticmethod
    def word():
        len_, word = Interp._word()
        Asm.push(word)
        Asm.push(len_)

    @staticmethod
    def _number(word, len_):
        if len_ == 0:
            return None, None

        unparsed = 0
        parsed = 0
        base = _vars["BASE"]
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
        len_ = Asm.pop()
        # Interp.word_buffer = [Asm.pop() for _ in range(len_)]
        word = [Asm.pop() for _ in range(len_)]

        found, errors = Interp._number(word, len_)

        # push parsed numbers and number of unparsed chars
        Asm.push(found)
        Asm.push(errors)

    @staticmethod
    def _find(word):
        word = ''.join(map(chr, word)).upper()
        ndx = _vars["LATEST"]
        while ndx is not None:
            flags = _dictionary[ndx + 1]
            if word == _dictionary[ndx + 2] and not flags & F_HIDDEN:
                break
            ndx = _dictionary[ndx]
        return ndx

    @staticmethod
    def find():
        len_ = Asm.pop()  # noqa
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
            Interp.tcfa,
            # TODO: inc esp here
            Interp.exit,
        ]

    @staticmethod
    def create():
        len_, name = Interp._word()

        # store latest as link
        _dictionary.append(_vars["LATEST"])

        # store word header
        _dictionary.extend([len_, ''.join(map(chr, name)).upper()])

        # update latest/here
        _vars["LATEST"], _vars["HERE"] = _vars["HERE"], len(_dictionary)

    @staticmethod
    def _comma(word):
        # append data to _dictionary and update HERE
        _dictionary.append(word)
        _vars["HERE"] = len(_dictionary)

    @staticmethod
    def comma():
        word = Asm.pop()
        Interp._comma(word)

    @staticmethod
    def rbrac():
        _vars["STATE"] = 1

    @staticmethod
    def lbrac():
        _vars["STATE"] = 0

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
        # TODO: LATEST
        _dictionary[-1][0] |= F_IMMED

    @staticmethod
    def hidden():
        ndx = Asm.pop()
        _dictionary[ndx + 1] ^= F_HIDDEN

    @staticmethod
    def hide():
        return [Interp._w2a("WORD"), Interp._w2a("FIND"),
                Interp._w2a("HIDDEN"), Interp._w2a("EXIT")]

    @staticmethod
    def tick():
        # TODO: make this work
        import pdb; pdb.set_trace()  # noqa
        addr = Asm.lodsl()                 # Get the address of the next word and skip it
        word = _dictionary[addr]
        Asm.push(word)

    @staticmethod
    def branch():
        # add (%esi),%esi         // add the offset to the instruction pointer
        pass

    @staticmethod
    def zbranch():
        # pop %eax
        # test %eax,%eax          // top of stack is zero?
        # jz code_BRANCH          // if so, jump back to the branch function above
        # lodsl                   // otherwise we need to skip the offset
        Asm.lodsl()

    @staticmethod
    def litstring():
        # lodsl                   // get the length of the string
        Asm.lodsl()
        # push %esi               // push the address of the start of the string
        # push %eax               // push it on the stack
        # addl %eax,%esi          // skip past the string
        # addl $3,%esi            // but round up to next 4 byte boundary
        # andl $~3,%esi

    @staticmethod
    def tell():
        # mov $1,%ebx             // 1st param: stdout
        # pop %edx                // 3rd param: length of string
        # pop %ecx                // 2nd param: address of string
        # mov $__NR_write,%eax    // write syscall
        # int $0x80
        pass

    @staticmethod
    def interpret_1(word, len_):
        # not in dict or a word, assume it's literal
        Interp.interpret_is_lit = 1
        raw_word = word
        word, errors = Interp._number(raw_word, len_)
        if errors:
            # TODO: deal number error/string
            # TODO: compiling runs here
            Interp.interpret_6(raw_word)
        elif word is not None:
            return word

    @staticmethod
    def interpret_2(addr):
        state = _vars["STATE"]
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
            # import pdb; pdb.set_trace()  # noqa
            Interp.interpret_5(addr)
        else:
            # execute word
            word = _dictionary[addr]
            if callable(word):
                word()
            else:
                # TODO: make variables functions
                # variable name retrieval
                Asm.push(addr)

    @staticmethod
    def interpret_5(literal):
        if literal is None:
            import pdb; pdb.set_trace()  # noqa
            return
        # push literal on stack
        Asm.push(literal)

    @staticmethod
    def interpret_6(word):
        global _data_stack
        print(f"PARSE ERROR: {''.join(list(map(chr, word)))}")
        # TODO: get input that failed
        _data_stack = []

    @staticmethod
    def interpret_7():
        # print something?
        pass

    @staticmethod
    def interpret():
        global esi
        while True:
            len_, word = Interp._word()
            Interp.interpret_is_lit = 0
            addr = Interp._find(word)
            found = addr
            if found is not None:
                addr = Interp._tcfa(addr)
                esi = addr
                if _dictionary[found + 1] & F_IMMED:
                    Interp.interpret_4(addr)
                else:
                    Interp.interpret_2(addr)
            else:
                addr = Interp.interpret_1(word, len_)
                Interp.interpret_2(addr)

    @staticmethod
    def quit():
        Interp.interpret()
        # Interp.branch(), -8

    @staticmethod
    def char():
        # TODO
        pass

    @staticmethod
    def execute():
        # TODO
        pass


class Asm:
    @staticmethod
    def push(reg):
        # inc data stack pointer - %ebp
        # move `reg` to %ebp
        _data_stack.append(reg)

    @staticmethod
    def pop():
        # dec data stack pointer - %ebp
        # move %ebp to `reg`
        return _data_stack.pop()

    @staticmethod
    def pushrsp(reg):
        # inc return stack pointer - %ebp
        # move `reg` to %ebp
        _return_stack.append(reg)

    @staticmethod
    def poprsp():
        # dec return stack pointer - %ebp
        # move %ebp to `reg`
        return _return_stack.pop()

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
        Asm.push(_data_stack[-1])

    @staticmethod
    def over():
        Asm.push(_data_stack[-2])

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
        _data_stack.extend(_data_stack[-2:])

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
        Asm.push(divmod(a, b))

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
        _return_stack.append(Asm.pop())

    @staticmethod
    def rto():
        Asm.push(_return_stack.pop())

    @staticmethod
    def rspat():
        Asm.push(_return_stack[-1])

    @staticmethod
    def rstor():
        _return_stack.append(Asm.pop())

    @staticmethod
    def rdrop():
        _return_stack.pop()

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
defvar("HERE", 4, lambda: Asm.push(_vars["HERE"]))
defcode("LATEST", 6, lambda: Asm.push(_vars["LATEST"]))
defvar("STATE", 5, 0)
defvar("S0", 2, "SZ")
defvar("BASE", 4, 10)


# --- CONSTANTS ---
defconst("VERSION", 7, "JONES_VERSION")
defconst("R0", 2, "return_stack_top")
defconst("DOCOL", 5, Interp.docol)
defconst("F_IMMED", 7, F_IMMED)
defconst("F_HIDDEN", 8, F_HIDDEN)
defconst("F_LENMASK", 9, F_LENMASK)


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


# --- STACK ---
defcode(">R", 2, Stack.tor)
defcode("R>", 2, Stack.rto)
defcode("RSP@", 4, Stack.rspat)
defcode("RSP!", 4, Stack.rstor)
defcode("RDROP", 5, Stack.rdrop)
defcode("DSP@", 4, Stack.dspat)
defcode("DSP!", 4, Stack.dspstor)


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
