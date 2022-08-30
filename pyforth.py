import sys

_data_stack = []
_return_stack = []
_dictionary = []

_vars = {"LATEST": None, "HERE": 0, "STATE": 0, "BASE": 10}
_const = {}

eax = None
ebx = None
ecx = None
esi = 0
edi = None


F_IMMED = 0x80
F_HIDDEN = 0x20
F_LENMASK = 0x1f     # length mask


def _start():
    global ebp, esi
    ebp = _return_stack
    esi = 0
    # INTERP.NEXT()                    # Run interpreter
    cold_start()


def cold_start():
    INTERP.QUIT()


# class Entry:
    # def __init__(self, link, name, namelen, label, flags=0):
        # self.link = link
        # self.name = name
        # self.namelen = namelen
        # self.label = label
        # self.flags = flags


def defword(name, namelen, code, flags=0):
    # link is start of previous entry in _dictionary
    link, _vars["LATEST"] = _vars["LATEST"], _vars["HERE"]
    _dictionary.extend([link, flags + namelen, name.upper(), INTERP.DOCOL])
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
    # PUSH $var_\name
    # ASM.PUSH(_vars['HERE'] - 1)
    # _vars[name.upper()] = initial
    # INTERP.NEXT()


def defconst(name, namelen, value, flags=0):
    defcode(name, namelen, value, flags)
    # PUSH $\value
    _const[name.upper()] = value
    # INTERP.NEXT()


# --- code for builtin forth words ---


class INTERP:
    input_buffer = []
    word_buffer = []
    docol_run = False

    @staticmethod
    def NEXT():
        ASM.LODSL()
        _dictionary[eax]()
        INTERP.docol_run = True

    @staticmethod
    def DOCOL():
        # push %esi on to return stack
        global eax, edi, esi
        ASM.PUSHRSP(esi)
        INTERP.docol_run = True
        esi = eax
        while INTERP.docol_run:
            esi += 1
            addr = _dictionary[esi]
            word = _dictionary[addr]
            word()
            edi = addr
        # INTERP.NEXT()

    @staticmethod
    def EXIT():
        global esi
        esi = ASM.POPRSP()
        INTERP.docol_run = False
        # INTERP.NEXT()

    @staticmethod
    def LIT():
        # %esi points to the next command, but in this case it points to the next
        # literal 32 bit integer. Get that literal into %eax and increment %esi.
        ASM.LODSL()
        # ASM.PUSH(eax)
        ASM.PUSH(_dictionary[esi])
        # INTERP.NEXT()

    @staticmethod
    def _KEY():
        global eax
        if not INTERP.input_buffer:
            INTERP.input_buffer = list(map(ord, sys.stdin.readline()))
            INTERP._KEY()
        else:
            eax = INTERP.input_buffer.pop(0)

    @staticmethod
    def KEY():
        INTERP._KEY()
        ASM.PUSH(eax)
        # INTERP.NEXT()

    @staticmethod
    def EMIT():
        print(chr(ASM.POP()), end="")
        # INTERP.NEXT()

    @staticmethod
    def _WORD():
        global eax, ecx, edi
        INTERP.word_buffer = []
        while True:
            INTERP._KEY()
            key = eax
            # start of comment
            if key == ord('\\'):
                # ignore everything to end of line
                while key != ord('\n'):
                    INTERP._KEY()
                    key = eax
            elif key > ord(' '):
                INTERP.word_buffer.append(key)
            else:
                break

        # save push word address and length
        edi = INTERP.word_buffer
        ecx = len(INTERP.word_buffer)

    @staticmethod
    def WORD():
        INTERP._WORD()
        # [ASM.PUSH(c) for c in edi]
        ASM.PUSH(edi)
        ASM.PUSH(ecx)
        # INTERP.NEXT()

    @staticmethod
    def _NUMBER():
        global eax, ebx, ecx
        if ecx == 0:
            return

        word = edi
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
        eax = neg * parsed
        ecx = unparsed

    @staticmethod
    def NUMBER():
        global ecx, edi
        ecx = ASM.POP()
        INTERP.word_buffer = [ASM.POP() for _ in range(ecx)]
        edi = INTERP.word_buffer

        INTERP._NUMBER()

        # push parsed numbers and number of unparsed chars
        ASM.PUSH(eax)
        ASM.PUSH(ecx)
        # INTERP.NEXT()

    @staticmethod
    def _FIND():
        global eax
        word = ''.join(map(chr, edi)).upper()
        ndx = _vars["LATEST"]
        while ndx is not None:
            # print(ndx, _dictionary[ndx+2])
            flags = _dictionary[ndx + 1]
            if word == _dictionary[ndx + 2] and not flags & F_HIDDEN:
                break
            else:
                ndx = _dictionary[ndx]
        eax = ndx

    @staticmethod
    def FIND():
        global eax, edi
        _ = ASM.POP()
        # edi = ''.join(map(chr, ASM.POP()))
        edi = ASM.POP()

        INTERP._FIND()

        ASM.PUSH(eax)
        # INTERP.NEXT()

    @staticmethod
    def _TCFA():
        global eax, edi
        edi += 3

    @staticmethod
    def TCFA():
        global edi
        edi = ASM.POP()

        INTERP._TCFA()

        ASM.PUSH(edi)
        # INTERP.NEXT()

    @staticmethod
    def TDFA():
        return [
            INTERP.TCFA,
            # TODO: inc esp here
            INTERP.EXIT,
        ]

    @staticmethod
    def CREATE():
        length, name = ASM.POP(), ''.join(map(chr, ASM.POP())).upper()

        # store latest as link
        _dictionary.append(_vars["LATEST"])

        # store word header
        _dictionary.extend([length, name])

        # update latest/here
        _vars["LATEST"], _vars["HERE"] = _vars["HERE"], len(_dictionary)
        # INTERP.NEXT()

    @staticmethod
    def _COMMA():
        global eax, edi
        # append data to _dictionary and update HERE
        edi = _vars["HERE"]
        _dictionary.append(eax)
        _vars["HERE"] = len(_dictionary)

    @staticmethod
    def COMMA():
        global eax
        eax = ASM.POP()

        INTERP._COMMA()

        # INTERP.NEXT()

    @staticmethod
    def RBRAC():
        _vars["STATE"] = 1
        # INTERP.NEXT()

    @staticmethod
    def LBRAC():
        _vars["STATE"] = 0
        # INTERP.NEXT()

    # def _word_to_addr(words):
    def _w2a(w):
        global eax, edi
        found = []
        # for w in words:
        if True:
            edi = list(map(ord, w))
            INTERP._FIND()
            edi = eax
            if not edi:
                import pdb; pdb.set_trace()  # noqa
            INTERP._TCFA()
            eax = edi
            found.append(eax)
        # return found
        return eax

    @staticmethod
    def COLON():
        # return [
            # INTERP.WORD,                    # get the name of the new word
            # INTERP.CREATE,                  # create the dictionary entry / header
            # INTERP.LIT, INTERP.DOCOL,
                # INTERP.COMMA,               # append DOCOL  (the codeword).
            # INTERP.LIT, _vars["LATEST"],
                # INTERP.HIDDEN,              # make the word hidden
            # INTERP.RBRAC,                   # go into compile mode.
            # INTERP.EXIT,                    # return from the function.
        # ]
        words = [
            INTERP._w2a("WORD"),                # get the name of the new word
            INTERP._w2a("CREATE"),              # create the dictionary entry / header
            INTERP._w2a("LIT"), INTERP.DOCOL,
                INTERP._w2a(","),               # append DOCOL  (the codeword).
            # INTERP._w2a("LIT"), INTERP._w2a("LATEST"),
            INTERP._w2a("LATEST"),
                # INTERP._w2a("@"),
                INTERP._w2a("HIDDEN"),          # make the word hidden
            INTERP._w2a("]"),                   # go into compile mode.
            INTERP._w2a("EXIT"),                # return from the function.
        ]
        # return INTERP._word_to_addr(words)
        return words

    @staticmethod
    def SEMICOLON():
        # return [
            # INTERP.LIT, INTERP.EXIT,
                # INTERP.COMMA,	            # append EXIT (so word will return)
            # INTERP.LIT, _vars["LATEST"],
                # INTERP.HIDDEN, 	            # toggle hidden flag -- unhide the word
            # INTERP.LBRAC,                   # go back to IMMEDIATE mode.
            # INTERP.EXIT,                    # return from the function.
        # ]
        words = [
            INTERP._w2a("LIT"), INTERP._w2a("EXIT"),
                INTERP._w2a(","),	            # append EXIT (so word will return)
            # INTERP._w2a("LIT"), _vars["LATEST"],
            INTERP._w2a("LATEST"),
                # INTERP._w2a("@"),
                INTERP._w2a("HIDDEN"), 	        # toggle hidden flag -- unhide the word
            INTERP._w2a("["),                   # go back to IMMEDIATE mode.
            INTERP._w2a("EXIT"),                # return from the function.
        ]
        # return INTERP._word_to_addr(words)
        return words

    @staticmethod
    def IMMEDIATE():
        _dictionary[-1][0] |= F_IMMED
        # INTERP.NEXT()

    @staticmethod
    def HIDDEN():
        ndx = ASM.POP()
        _dictionary[ndx + 1] ^= F_HIDDEN
        # INTERP.NEXT()

    @staticmethod
    def HIDE():
        # return [INTERP.WORD, INTERP.FIND, INTERP.HIDDEN, INTERP.EXIT]
        # return INTERP._word_to_addr(["WORD", "FIND", "HIDDEN", "EXIT"])
        return [INTERP._w2a("WORD"), INTERP._w2a("FIND"),
                INTERP._w2a("HIDDEN"), INTERP._w2a("EXIT")]

    @staticmethod
    def TICK():
        # lodsl                   // Get the address of the next word and skip it.
        ASM.LODSL()
        word = _dictionary[eax]
        ASM.PUSH(word)
        # INTERP.NEXT()

    @staticmethod
    def BRANCH():
        # add (%esi),%esi         // add the offset to the instruction pointer
        # INTERP.NEXT()
        pass

    @staticmethod
    def ZBRANCH():
        # pop %eax
        # test %eax,%eax          // top of stack is zero?
        # jz code_BRANCH          // if so, jump back to the branch function above
        # lodsl                   // otherwise we need to skip the offset
        ASM.LODSL()
        # INTERP.NEXT()

    @staticmethod
    def LITSTRING():
        # lodsl                   // get the length of the string
        ASM.LODSL()
        # push %esi               // push the address of the start of the string
        # push %eax               // push it on the stack
        # addl %eax,%esi          // skip past the string
        # addl $3,%esi            // but round up to next 4 byte boundary
        # andl $~3,%esi
        # INTERP.NEXT()

    @staticmethod
    def TELL():
        # mov $1,%ebx             // 1st param: stdout
        # pop %edx                // 3rd param: length of string
        # pop %ecx                // 2nd param: address of string
        # mov $__NR_write,%eax    // write syscall
        # int $0x80
        # INTERP.NEXT()
        pass

    interpret_is_lit = 0

    @staticmethod
    def INTERPRET_1():
        global eax, ebx
        # not in dict or a word, assume it's literal
        INTERP.interpret_is_lit = 1
        INTERP._NUMBER()
        errors = ecx
        if errors:
            # TODO: deal number error/string
            # TODO: compiling runs here
            # INTERP.INTERPRET_6()
            # assume string - should be address
            ASM.PUSH(edi)
            eax = len(edi)
        else:
            ebx = eax
            # eax = INTERP.LIT
            eax = INTERP._w2a("LIT")

    @staticmethod
    def INTERPRET_2():
        global eax
        state = _vars["STATE"]
        if state:
            # compiling
            INTERP._COMMA()
            if INTERP.interpret_is_lit:
                eax = ebx
                INTERP._COMMA()
            else:
                INTERP.INTERPRET_3()
        else:
            INTERP.INTERPRET_4()

    @staticmethod
    def INTERPRET_3():
        # INTERP.NEXT()
        pass

    @staticmethod
    def INTERPRET_4():
        if INTERP.interpret_is_lit:
            INTERP.INTERPRET_5()
        else:
            # execute word
            word = _dictionary[edi]
            if callable(word):
                word()
            else:
                ASM.PUSH(edi)

    @staticmethod
    def INTERPRET_5():
        global ebx
        if not ebx:
            import pdb; pdb.set_trace()  # noqa
        # push literal on stack
        ASM.PUSH(ebx)
        # INTERP.NEXT()

    @staticmethod
    def INTERPRET_6():
        print("PARSE ERROR: ")
        # TODO: get input that failed

    @staticmethod
    def INTERPRET_7():
        # print something?
        pass

    @staticmethod
    def INTERPRET():
        global eax, edi
        while True:
            INTERP._WORD()
            INTERP.interpret_is_lit = 0
            INTERP._FIND()
            found = eax
            # import pdb; pdb.set_trace()  # noqa
            # print(found)
            if found is not None:
                edi = eax
                # get name/flags
                eax = _dictionary[found + 1]
                ASM.PUSH(eax)
                INTERP._TCFA()
                eax = ASM.POP()
                eax = edi
                # import pdb; pdb.set_trace()  # noqa
                if _dictionary[found + 1] & F_IMMED:
                    INTERP.INTERPRET_4()
                else:
                    INTERP.INTERPRET_2()
            else:
                INTERP.INTERPRET_1()
                INTERP.INTERPRET_2()

    @staticmethod
    def QUIT():
        INTERP.INTERPRET()
        # INTERP.BRANCH(), -8

    @staticmethod
    def CHAR():
        # TODO
        pass

    @staticmethod
    def EXECUTE():
        # TODO
        pass


class ASM:
    @staticmethod
    def PUSH(reg):
        # inc data stack pointer - %ebp
        # move `reg` to %ebp
        if reg is None:
            import pdb; pdb.set_trace()  # noqa
            print("why is it push None")
        _data_stack.append(reg)

    @staticmethod
    def POP():
        # dec data stack pointer - %ebp
        # move %ebp to `reg`
        return _data_stack.pop()

    @staticmethod
    def PUSHRSP(reg):
        # inc return stack pointer - %ebp
        # move `reg` to %ebp
        _return_stack.append(reg)

    @staticmethod
    def POPRSP():
        # dec return stack pointer - %ebp
        # move %ebp to `reg`
        return _return_stack.pop()

    @staticmethod
    def LODSL():
        global eax, esi
        # load %esi into %eax, increment %esi
        eax = esi
        esi += 1


class MANIPULATORS:
    @staticmethod
    def DROP():
        ASM.POP()
        # INTERP.NEXT()

    @staticmethod
    def SWAP():
        a, b = ASM.POP(), ASM.POP()
        ASM.PUSH(a)
        ASM.PUSH(b)
        # INTERP.NEXT()

    @staticmethod
    def DUP():
        ASM.PUSH(_data_stack[-1])
        # INTERP.NEXT()

    @staticmethod
    def OVER():
        ASM.PUSH(_data_stack[-2])
        # INTERP.NEXT()

    @staticmethod
    def ROT():
        a, b, c = ASM.POP(), ASM.POP(), ASM.POP()
        ASM.PUSH(b)
        ASM.PUSH(a)
        ASM.PUSH(c)
        # INTERP.NEXT()

    @staticmethod
    def INVROT():
        a, b, c = ASM.POP(), ASM.POP(), ASM.POP()
        ASM.PUSH(a)
        ASM.PUSH(c)
        ASM.PUSH(b)
        # INTERP.NEXT()

    @staticmethod
    def DDROP():
        ASM.POP()
        ASM.POP()
        # INTERP.NEXT()

    @staticmethod
    def DSWAP():
        a, b, c, d = ASM.POP(), ASM.POP(), ASM.POP(), ASM.POP()
        ASM.PUSH(b)
        ASM.PUSH(a)
        ASM.PUSH(d)
        ASM.PUSH(c)
        # INTERP.NEXT()

    @staticmethod
    def DDUP():
        _data_stack.extend(_data_stack[-2:])
        # INTERP.NEXT()

    @staticmethod
    def QDUP():
        d = ASM.POP()
        if d:
            ASM.PUSH(d)
            ASM.PUSH(d)
        # INTERP.NEXT()

    @staticmethod
    def ONEP():
        ASM.PUSH(ASM.POP() + 1)
        # INTERP.NEXT()

    @staticmethod
    def ONEM():
        ASM.PUSH(ASM.POP() - 1)
        # INTERP.NEXT()

    @staticmethod
    def PLUS():
        a, b = ASM.POP(), ASM.POP()
        ASM.PUSH(a + b)
        # INTERP.NEXT()

    @staticmethod
    def SUB():
        a, b = ASM.POP(), ASM.POP()
        ASM.PUSH(a - b)
        # INTERP.NEXT()

    @staticmethod
    def MUL():
        a, b = ASM.POP(), ASM.POP()
        ASM.PUSH(a * b)
        # INTERP.NEXT()

    @staticmethod
    def DIVMOD():
        a, b = ASM.POP(), ASM.POP()
        ASM.PUSH(divmod(a, b))
        # INTERP.NEXT()

    @staticmethod
    def EQUAL():
        a, b = ASM.POP(), ASM.POP()
        ASM.PUSH(a == b)
        # INTERP.NEXT()

    @staticmethod
    def NEQ():
        a, b = ASM.POP(), ASM.POP()
        ASM.PUSH(a != b)
        # INTERP.NEXT()

    @staticmethod
    def LT():
        a, b = ASM.POP(), ASM.POP()
        ASM.PUSH(a < b)
        # INTERP.NEXT()

    @staticmethod
    def GT():
        a, b = ASM.POP(), ASM.POP()
        ASM.PUSH(a > b)
        # INTERP.NEXT()

    @staticmethod
    def LEQ():
        a, b = ASM.POP(), ASM.POP()
        ASM.PUSH(a <= b)
        # INTERP.NEXT()

    @staticmethod
    def GEQ():
        a, b = ASM.POP(), ASM.POP()
        ASM.PUSH(a >= b)
        # INTERP.NEXT()

    @staticmethod
    def ZEQ():
        a = ASM.POP()
        ASM.PUSH(a == 0)
        # INTERP.NEXT()

    @staticmethod
    def ZNEQ():
        a = ASM.POP()
        ASM.PUSh(a != 0)
        # INTERP.NEXT()

    @staticmethod
    def ZLT():
        a = ASM.POP()
        ASM.PUSH(a < 0)
        # INTERP.NEXT()

    @staticmethod
    def ZLEQ():
        a = ASM.POP()
        ASM.PUSH(a <= 0)
        # INTERP.NEXT()

    @staticmethod
    def ZGT():
        a = ASM.POP()
        ASM.PUSH(a > 0)
        # INTERP.NEXT()

    @staticmethod
    def ZGEQ():
        a = ASM.POP()
        ASM.PUSH(a >= 0)
        # INTERP.NEXT()

    @staticmethod
    def AND():
        a, b = ASM.POP(), ASM.POP()
        ASM.PUSH(a & b)
        # INTERP.NEXT()

    @staticmethod
    def OR():
        a, b = ASM.POP(), ASM.POP()
        ASM.PUSH(a | b)
        # INTERP.NEXT()

    @staticmethod
    def XOR():
        a, b = ASM.POP(), ASM.POP()
        ASM.PUSH(a ^ b)
        # INTERP.NEXT()

    @staticmethod
    def INV():
        ASM.PUSH(-ASM.POP())
        # INTERP.NEXT()


class STACK:
    @staticmethod
    def TOR():
        _return_stack.append(ASM.POP())
        # INTERP.NEXT()

    @staticmethod
    def RTO():
        ASM.PUSH(_return_stack.pop())
        # INTERP.NEXT()

    @staticmethod
    def RSPAT():
        ASM.PUSH(_return_stack[-1])
        # INTERP.NEXT()

    @staticmethod
    def RSTOR():
        _return_stack.append(ASM.POP())
        # INTERP.NEXT()

    @staticmethod
    def RDROP():
        _return_stack.pop()
        # INTERP.NEXT()

    @staticmethod
    def DSPAT():
        # mov %esp,%eax
        # push %eax
        print("TODO: DSPAT")
        # INTERP.NEXT()

    @staticmethod
    def DSPSTOR():
        # pop %esp
        print("TODO: DSPAT")
        INTERP.NEXT()


class MEMORY:
    @staticmethod
    def STOR():
        ebx = ASM.POP()                 # address to store at
        eax = ASM.POP()                 # data to store there
        _dictionary[ebx] = eax          # store it
        # INTERP.NEXT()

    @staticmethod
    def FETCH():
        global eax, ebx
        ebx = ASM.POP()             # address to fetch
        eax = _dictionary[ebx]      # fetch it
        ASM.PUSH(eax)               # push value onto stack
        # INTERP.NEXT()

    @staticmethod
    def PSTOR():
        global eax, ebx
        ebx = ASM.POP()             # address
        eax = ASM.POP()             # the amount to add
        _dictionary[ebx] += eax
        # INTERP.NEXT()

    @staticmethod
    def MSTOR():
        global eax, ebx
        ebx = ASM.POP()             # address
        eax = ASM.POP()             # the amount to add
        _dictionary[ebx] -= eax
        # INTERP.NEXT()

    @staticmethod
    def CSTOR():
        # pop %ebx                // address to store at
        # pop %eax                // data to store there
        # movb %al,(%ebx)         // store it
        # INTERP.NEXT()
        pass

    @staticmethod
    def CAT():
        # pop %ebx                // address to fetch
        # xor %eax,%eax
        # movb (%ebx),%al         // fetch it
        # push %eax               // push value onto stack
        # INTERP.NEXT()
        pass

    # #(/* C@C! is a useful byte copy primitive. */
    # defcode("C@C!", 4, "
            # movl 4(%esp),%ebx       // source address
            # movb (%ebx),%al         // get source character
            # pop %edi                // destination address
            # stosb                   // copy to destination
            # push %edi               // increment destination address
            # incl 4(%esp)            // increment source address
            # INTERP.NEXT")

    @staticmethod
    def CMOVE():
        # mov %esi,%edx           // preserve %esi
        # pop %ecx                // length
        # pop %edi                // destination address
        # pop %esi                // source address
        # rep movsb               // copy source to destination
        # mov %edx,%esi           // restore %esi
        # INTERP.NEXT()
        pass


# --- VARIABLES ---
# hard coded to point to end of _dictionary
defvar("HERE", 4, 360)
# defvar("LATEST", 6, 356)
defcode("LATEST", 6, lambda: ASM.PUSH(_vars["LATEST"]))
defvar("STATE", 5, 0)
defvar("S0", 2, "SZ")
defvar("BASE", 4, 10)


# --- CONSTANTS ---
defconst("VERSION", 7, "JONES_VERSION")
defconst("R0", 2, "return_stack_top")
defconst("DOCOL", 5, INTERP.DOCOL)
defconst("F_IMMED", 7, F_IMMED)
defconst("F_HIDDEN", 8, F_HIDDEN)
defconst("F_LENMASK", 9, F_LENMASK)


# --- MEMORY ---
defcode("!", 1, MEMORY.STOR)
defcode("@", 5, MEMORY.FETCH)
defcode("+!", 2, MEMORY.PSTOR)
defcode("-!", 2, MEMORY.MSTOR)
defcode("C!", 2, MEMORY.CSTOR)
defcode("C@", 2, MEMORY.CAT)
# c@c! is a useful byte copy primitive.
# defcode("C@C!", 4, MEMORY.)
# and CMOVE is a block copy operation.
defcode("CMOVE", 5, MEMORY.CMOVE)


defcode("EXIT", 4, INTERP.EXIT)
defcode("LIT", 3, INTERP.LIT)
defcode("KEY", 3, INTERP.KEY)
defcode("WORD", 4, INTERP.WORD)
defcode("EMIT", 4, INTERP.EMIT)
defcode("FIND", 4, INTERP.FIND)
defcode(">CFA", 4, INTERP.TCFA)
defword(">DFA", 4, INTERP.TDFA)
defcode("CREATE", 6, INTERP.CREATE)
defcode(",", 1, INTERP.COMMA)
defcode("[", 1, INTERP.LBRAC, flags=F_IMMED)
defcode("]", 1, INTERP.RBRAC)
defcode("IMMEDIATE", 9, INTERP.IMMEDIATE, flags=F_IMMED)
defcode("HIDDEN", 6, INTERP.HIDDEN)
defcode("BRANCH", 6, INTERP.BRANCH)
defcode("0BRANCH", 7, INTERP.ZBRANCH)
defcode("LITSTRING", 9, INTERP.LITSTRING)
defcode("TELL", 4, INTERP.TELL)
defcode("INTERPRET", 9, INTERP.INTERPRET)
defcode("CHAR", 4, INTERP.CHAR)
defcode("EXECUTE", 7, INTERP.EXECUTE)
defword("HIDE", 4, INTERP.HIDE)
defword(":", 1, INTERP.COLON)
defword(";", 1, INTERP.SEMICOLON, flags=F_IMMED)


# --- MANIPULATORS ---
defcode("DROP", 4, MANIPULATORS.DROP)
defcode("SWAP", 4, MANIPULATORS.SWAP)
defcode("DUP", 3, MANIPULATORS.DUP)
defcode("OVER", 4, MANIPULATORS.OVER)
defcode("ROT", 3, MANIPULATORS.ROT)
defcode("-ROT", 4, MANIPULATORS.INVROT)
defcode("2DUP", 4, MANIPULATORS.DDUP)
defcode("2DROP", 5, MANIPULATORS.DDROP)
defcode("2SWAP", 5, MANIPULATORS.DSWAP)
defcode("?DUP", 4, MANIPULATORS.QDUP)
defcode("1+", 2, MANIPULATORS.ONEP)
defcode("1-", 2, MANIPULATORS.ONEM)
# defcode("4+", 2, "
        # addl $4,(%esp)          // add 4 to top of stack
        # INTERP.NEXT")
# defcode("4-", 2, "
        # subl $4,(%esp)          // subtract 4 from top of stack
        # INTERP.NEXT")
defcode("+", 1, MANIPULATORS.PLUS)
defcode("-", 1, MANIPULATORS.SUB)
defcode("*", 1, MANIPULATORS.MUL)
defcode("/MOD", 4, MANIPULATORS.DIVMOD)
defcode("=", 1, MANIPULATORS.EQUAL)
defcode("<>", 2, MANIPULATORS.NEQ)
defcode("<", 1, MANIPULATORS.LT)
defcode(">", 1, MANIPULATORS.GT)
defcode("<=", 2, MANIPULATORS.LEQ)
defcode(">=", 2, MANIPULATORS.GEQ)
defcode("0=", 2, MANIPULATORS.ZEQ)
defcode("0<>", 3, MANIPULATORS.ZNEQ)
defcode("0<", 2, MANIPULATORS.ZLT)
defcode("0>", 2, MANIPULATORS.ZGT)
defcode("0<=", 3, MANIPULATORS.ZLEQ)
defcode("0>=", 3, MANIPULATORS.ZGEQ)
defcode("AND", 3, MANIPULATORS.AND)
defcode("OR", 2, MANIPULATORS.OR)
defcode("XOR", 3, MANIPULATORS.XOR)
defcode("INVERT", 6, MANIPULATORS.INV)


# --- STACK ---
defcode(">R", 2, STACK.TOR)
defcode("R>", 2, STACK.RTO)
defcode("RSP@", 4, STACK.RSPAT)
defcode("RSP!", 4, STACK.RSTOR)
defcode("RDROP", 5, STACK.RDROP)
defcode("DSP@", 4, STACK.DSPAT)
defcode("DSP!", 4, STACK.DSPSTOR)


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
