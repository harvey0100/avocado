#  Copyright (c) 1998-2002 John Aycock
#
#  Permission is hereby granted, free of charge, to any person obtaining
#  a copy of this software and associated documentation files (the
#  "Software"), to deal in the Software without restriction, including
#  without limitation the rights to use, copy, modify, merge, publish,
#  distribute, sublicense, and/or sell copies of the Software, and to
#  permit persons to whom the Software is furnished to do so, subject to
#  the following conditions:
#
#  The above copyright notice and this permission notice shall be
#  included in all copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
#  EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
#  MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
#  CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
#  TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#  SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

__version__ = "SPARK-0.7 (pre-alpha-7)"

import re


def _namelist(instance):
    namelist, namedict, classlist = [], {}, [instance.__class__]
    for c in classlist:
        for b in c.__bases__:
            classlist.append(b)  # pylint: disable=W4701
        for name in c.__dict__.keys():
            if name not in namedict:
                namelist.append(name)
                namedict[name] = 1
    return namelist


class GenericScanner:
    def __init__(self, flags=0):
        pattern = self.reflect()
        self.re = re.compile(pattern, re.VERBOSE | flags)

        self.index2func = {}
        for name, number in self.re.groupindex.items():
            self.index2func[number - 1] = getattr(self, "t_" + name)

    def makeRE(self, name):  # pylint: disable=C0103
        doc = getattr(self, name).__doc__
        rv = f"(?P<{name[2:]}>{doc})"
        return rv

    def reflect(self):
        rv = []
        for name in _namelist(self):
            if name[:2] == "t_" and name != "t_default":
                rv.append(self.makeRE(name))

        rv.append(self.makeRE("t_default"))
        return "|".join(rv)

    @staticmethod
    def error(s, pos):  # pylint: disable=W0613
        print(f"Lexical error at position {pos}")
        raise SystemExit

    def tokenize(self, s):
        pos = 0
        n = len(s)
        while pos < n:
            m = self.re.match(s, pos)
            if m is None:
                self.error(s, pos)

            groups = m.groups()
            for i, group in enumerate(groups):
                if group and i in self.index2func:
                    self.index2func[i](group)
            pos = m.end()

    @staticmethod
    def t_default(s):  # pylint: disable=W0613
        r"( . | \n )+"
        print("Specification error: unmatched input")
        raise SystemExit


#
#  Extracted from GenericParser and made global so that [un]picking works.
#


class _State:
    def __init__(self, stateno, items):
        self.t, self.complete, self.items = [], [], items
        self.stateno = stateno


# pylint: disable=R0902,R0904
class GenericParser:
    #
    #  An Earley parser, as per J. Earley, "An Efficient Context-Free
    #  Parsing Algorithm", CACM 13(2), pp. 94-102.  Also J. C. Earley,
    #  "An Efficient Context-Free Parsing Algorithm", Ph.D. thesis,
    #  Carnegie-Mellon University, August 1968.  New formulation of
    #  the parser according to J. Aycock, "Practical Earley Parsing
    #  and the SPARK Toolkit", Ph.D. thesis, University of Victoria,
    #  2001, and J. Aycock and R. N. Horspool, "Practical Earley
    #  Parsing", unpublished paper, 2001.
    #

    def __init__(self, start):
        self.rules = {}
        self.rule2func = {}
        self.rule2name = {}
        self.collectRules()
        self.augment(start)
        self.ruleschanged = 1

    _NULLABLE = r"\e_"
    _START = "START"
    _BOF = "|-"

    #
    #  When pickling, take the time to generate the full state machine;
    #  some information is then extraneous, too.  Unfortunately we
    #  can't save the rule2func map.
    #
    def __getstate__(self):
        if self.ruleschanged:
            #
            #  FIX ME - duplicated from parse()
            #
            self.computeNull()
            self.newrules = {}  # pylint: disable=W0201
            self.new2old = {}  # pylint: disable=W0201
            self.makeNewRules()
            self.ruleschanged = 0
            self.edges, self.cores = {}, {}  # pylint: disable=W0201
            self.states = {0: self.makeState0()}  # pylint: disable=W0201
            self.makeState(0, self._BOF)
        #
        #  FIX ME - should find a better way to do this..
        #
        changes = 1
        while changes:
            changes = 0
            for k, v in self.edges.items():
                if v is None:
                    state, sym = k
                    if state in self.states:
                        self.goto(state, sym)
                        changes = 1
        rv = self.__dict__.copy()
        for s in self.states.values():
            del s.items
        del rv["rule2func"]
        del rv["nullable"]
        del rv["cores"]
        return rv

    def __setstate__(self, d):
        self.rules = {}
        self.rule2func = {}
        self.rule2name = {}
        self.collectRules()
        start = d["rules"][self._START][0][1][1]  # Blech.
        self.augment(start)
        d["rule2func"] = self.rule2func
        d["makeSet"] = self.makeSet_fast
        self.__dict__ = d  # pylint: disable=W0201

    #
    #  A hook for GenericASTBuilder and GenericASTMatcher.  Mess
    #  thee not with this; nor shall thee toucheth the _preprocess
    #  argument to addRule.
    #
    @staticmethod
    def preprocess(rule, func):
        return rule, func

    def addRule(self, doc, func, _preprocess=1):  # pylint: disable=C0103
        fn = func
        rules = doc.split()

        index = []
        for i, rule in enumerate(rules):
            if rule == "::=":
                index.append(i - 1)
        index.append(len(rules))

        for i in range(len(index) - 1):
            lhs = rules[index[i]]
            rhs = rules[index[i] + 2 : index[i + 1]]
            rule = (lhs, tuple(rhs))

            if _preprocess:
                rule, fn = self.preprocess(rule, func)

            if lhs in self.rules:
                self.rules[lhs].append(rule)
            else:
                self.rules[lhs] = [rule]
            self.rule2func[rule] = fn
            self.rule2name[rule] = func.__name__[2:]
        self.ruleschanged = 1

    def collectRules(self):  # pylint: disable=C0103
        for name in _namelist(self):
            if name[:2] == "p_":
                func = getattr(self, name)
                doc = func.__doc__
                self.addRule(doc, func)

    def augment(self, start):
        rule = f"{self._START} ::= {self._BOF} {start}"
        self.addRule(rule, lambda args: args[1], 0)

    def computeNull(self):  # pylint: disable=C0103
        self.nullable = {}  # pylint: disable=W0201
        tbd = []

        for rulelist in self.rules.values():
            lhs = rulelist[0][0]
            self.nullable[lhs] = 0
            for rule in rulelist:
                rhs = rule[1]
                if not rhs:
                    self.nullable[lhs] = 1
                    continue
                #
                #  We only need to consider rules which
                #  consist entirely of nonterminal symbols.
                #  This should be a savings on typical
                #  grammars.
                #
                for sym in rhs:
                    if sym not in self.rules:
                        break
                else:
                    tbd.append(rule)
        changes = 1
        while changes:
            changes = 0
            for lhs, rhs in tbd:
                if self.nullable[lhs]:
                    continue
                for sym in rhs:
                    if not self.nullable[sym]:
                        break
                else:
                    self.nullable[lhs] = 1
                    changes = 1

    def makeState0(self):  # pylint: disable=C0103
        s0 = _State(0, [])
        for rule in self.newrules[self._START]:
            s0.items.append((rule, 0))
        return s0

    def finalState(self, tokens):  # pylint: disable=C0103
        #
        #  Yuck.
        #
        if len(self.newrules[self._START]) == 2 and not tokens:
            return 1
        start = self.rules[self._START][0][1][1]
        return self.goto(1, start)

    def makeNewRules(self):  # pylint: disable=C0103
        worklist = []
        for rulelist in self.rules.values():
            for rule in rulelist:
                worklist.append((rule, 0, 1, rule))

        for rule, i, candidate, oldrule in worklist:
            lhs, rhs = rule
            n = len(rhs)
            while i < n:
                sym = rhs[i]
                if sym not in self.rules or not self.nullable[sym]:
                    candidate = 0
                    i += 1
                    continue

                newrhs = list(rhs)
                newrhs[i] = self._NULLABLE + sym
                newrule = (lhs, tuple(newrhs))
                # pylint: disable=W4701
                worklist.append((newrule, i + 1, candidate, oldrule))
                candidate = 0
                i += 1
            else:  # pylint: disable=W0120
                if candidate:
                    lhs = self._NULLABLE + lhs
                    rule = (lhs, rhs)
                if lhs in self.newrules:
                    self.newrules[lhs].append(rule)
                else:
                    self.newrules[lhs] = [rule]
                self.new2old[rule] = oldrule

    @staticmethod
    def typestring(token):  # pylint: disable=W0613
        return None

    @staticmethod
    def error(token):
        print(f"Syntax error at or near `{token}' token")
        raise SystemExit

    def parse(self, tokens):
        sets = [[(1, 0), (2, 0)]]
        self.links = {}  # pylint: disable=W0201

        if self.ruleschanged:
            self.computeNull()
            self.newrules = {}  # pylint: disable=W0201
            self.new2old = {}  # pylint: disable=W0201
            self.makeNewRules()
            self.ruleschanged = 0
            self.edges, self.cores = {}, {}  # pylint: disable=W0201
            self.states = {0: self.makeState0()}  # pylint: disable=W0201
            self.makeState(0, self._BOF)

        for i, token in enumerate(tokens):
            sets.append([])

            if sets[i] == []:
                break
            self.makeSet(token, sets, i)
        else:
            sets.append([])
            self.makeSet(None, sets, len(tokens))

        finalitem = (self.finalState(tokens), 0)
        if finalitem not in sets[-2]:
            if len(tokens) > 0:
                self.error(tokens[i - 1])  # pylint: disable=W0631
            else:
                self.error(None)

        return self.buildTree(self._START, finalitem, tokens, len(sets) - 2)

    def isnullable(self, sym):
        #
        #  For symbols in G_e only.  If we weren't supporting 1.5,
        #  could just use sym.startswith().
        #
        return self._NULLABLE == sym[0 : len(self._NULLABLE)]

    def skip(self, hs, pos=0):
        n = len(hs[1])
        while pos < n:
            if not self.isnullable(hs[1][pos]):
                break
            pos += 1
        return pos

    def makeState(self, state, sym):  # pylint: disable=R0914, R0912, C0103
        assert sym is not None
        #
        #  Compute \epsilon-kernel state's core and see if
        #  it exists already.
        #
        kitems = []
        for rule, pos in self.states[state].items:
            _, rhs = rule
            if rhs[pos : pos + 1] == (sym,):
                kitems.append((rule, self.skip(rule, pos + 1)))
        core = kitems

        core.sort()
        tcore = tuple(core)
        if tcore in self.cores:
            return self.cores[tcore]
        #
        #  Nope, doesn't exist.  Compute it and the associated
        #  \epsilon-nonkernel state together; we'll need it right away.
        #
        k = self.cores[tcore] = len(self.states)
        ks, nk = _State(k, kitems), _State(k + 1, [])
        self.states[k] = ks
        predicted = {}

        edges = self.edges
        rules = self.newrules
        for x in ks, nk:
            worklist = x.items
            for item in worklist:
                rule, pos = item
                _, rhs = rule
                if pos == len(rhs):
                    x.complete.append(rule)
                    continue

                next_sym = rhs[pos]
                key = (x.stateno, next_sym)
                if next_sym not in rules:
                    if key not in edges:
                        edges[key] = None
                        x.t.append(next_sym)
                else:
                    edges[key] = None
                    if next_sym not in predicted:
                        predicted[next_sym] = 1
                        for prule in rules[next_sym]:
                            ppos = self.skip(prule)
                            new = (prule, ppos)
                            nk.items.append(new)
            #
            #  Problem: we know K needs generating, but we
            #  don't yet know about NK.  Can't commit anything
            #  regarding NK to self.edges until we're sure.  Should
            #  we delay committing on both K and NK to avoid this
            #  hacky code?  This creates other problems..
            #
            if x is ks:
                edges = {}

        if nk.items == []:
            return k

        #
        #  Check for \epsilon-nonkernel's core.  Unfortunately we
        #  need to know the entire set of predicted nonterminals
        #  to do this without accidentally duplicating states.
        #
        core = sorted(predicted.keys())
        tcore = tuple(core)
        if tcore in self.cores:
            self.edges[(k, None)] = self.cores[tcore]
            return k

        nk = self.cores[tcore] = self.edges[(k, None)] = nk.stateno
        self.edges.update(edges)
        self.states[nk] = nk
        return k

    def goto(self, state, sym):
        key = (state, sym)
        if key not in self.edges:
            #
            #  No transitions from state on sym.
            #
            return None

        rv = self.edges[key]
        if rv is None:
            #
            #  Target state isn't generated yet.  Remedy this.
            #
            rv = self.makeState(state, sym)
            self.edges[key] = rv
        return rv

    def gotoT(self, state, t):  # pylint: disable=C0103
        return [self.goto(state, t)]

    def gotoST(self, state, st):  # pylint: disable=C0103
        rv = []
        for t in self.states[state].t:
            if st == t:
                rv.append(self.goto(state, t))
        return rv

    # pylint: disable=R0913
    def add(self, input_set, item, i=None, predecessor=None, causal=None):
        if predecessor is None:
            if item not in input_set:
                input_set.append(item)
        else:
            key = (item, i)
            if item not in input_set:
                self.links[key] = []
                input_set.append(item)
            self.links[key].append((predecessor, causal))

    def makeSet(self, token, sets, i):  # pylint: disable=R0914,C0103
        cur, next_item = sets[i], sets[i + 1]

        ttype = (  # pylint: disable=R1709
            token is not None and self.typestring(token) or None
        )
        if ttype is not None:
            fn, arg = self.gotoT, ttype
        else:
            fn, arg = self.gotoST, token

        for item in cur:
            ptr = (item, i)
            state, parent = item
            add = fn(state, arg)
            for k in add:
                if k is not None:
                    self.add(next_item, (k, parent), i + 1, ptr)
                    nk = self.goto(k, None)
                    if nk is not None:
                        self.add(next_item, (nk, i + 1))

            if parent == i:
                continue

            for rule in self.states[state].complete:
                lhs, _ = rule
                for pitem in sets[parent]:
                    pstate, pparent = pitem
                    k = self.goto(pstate, lhs)
                    if k is not None:
                        why = (item, i, rule)
                        pptr = (pitem, parent)
                        self.add(cur, (k, pparent), i, pptr, why)
                        nk = self.goto(k, None)
                        if nk is not None:
                            self.add(cur, (nk, i))

    def makeSet_fast(self, token, sets, i):  # pylint: disable=R0914, R0912, C0103
        #
        #  Call *only* when the entire state machine has been built!
        #  It relies on self.edges being filled in completely, and
        #  then duplicates and inlines code to boost speed at the
        #  cost of extreme ugliness.
        #
        cur, next_item = sets[i], sets[i + 1]
        ttype = (  # pylint: disable=R1709
            token is not None and self.typestring(token) or None
        )

        for item in cur:  # pylint: disable=R1702
            ptr = (item, i)
            state, parent = item
            if ttype is not None:
                k = self.edges.get((state, ttype), None)
                if k is not None:
                    # self.add(next_item, (k, parent), i + 1, ptr)
                    # INLINED --v
                    new = (k, parent)
                    key = (new, i + 1)
                    if new not in next_item:
                        self.links[key] = []
                        next_item.append(new)
                    self.links[key].append((ptr, None))
                    # INLINED --^
                    # nk = self.goto(k, None)
                    nk = self.edges.get((k, None), None)
                    if nk is not None:
                        # self.add(next_item, (nk, i + 1))
                        # INLINED --v
                        new = (nk, i + 1)
                        if new not in next_item:
                            next_item.append(new)
                        # INLINED --^
            else:
                add = self.gotoST(state, token)
                for k in add:
                    if k is not None:
                        self.add(next_item, (k, parent), i + 1, ptr)
                        # nk = self.goto(k, None)
                        nk = self.edges.get((k, None), None)
                        if nk is not None:
                            self.add(next_item, (nk, i + 1))

            if parent == i:
                continue

            for rule in self.states[state].complete:
                lhs, _ = rule
                for pitem in sets[parent]:
                    pstate, pparent = pitem
                    # k = self.goto(pstate, lhs)
                    k = self.edges.get((pstate, lhs), None)
                    if k is not None:
                        why = (item, i, rule)
                        pptr = (pitem, parent)
                        # self.add(cur, (k, pparent),
                        #          i, pptr, why)
                        # INLINED --v
                        new = (k, pparent)
                        key = (new, i)
                        if new not in cur:
                            self.links[key] = []
                            cur.append(new)
                        self.links[key].append((pptr, why))
                        # INLINED --^
                        # nk = self.goto(k, None)
                        nk = self.edges.get((k, None), None)
                        if nk is not None:
                            # self.add(cur, (nk, i))
                            # INLINED --v
                            new = (nk, i)
                            if new not in cur:
                                cur.append(new)
                            # INLINED --^

    def predecessor(self, key, causal):
        for p, c in self.links[key]:
            if c == causal:
                return p
        assert 0

    def causal(self, key):
        links = self.links[key]
        if len(links) == 1:
            return links[0][1]
        choices = []
        rule2cause = {}
        for _, c in links:
            rule = c[2]
            choices.append(rule)
            rule2cause[rule] = c
        return rule2cause[self.ambiguity(choices)]

    def deriveEpsilon(self, nt):  # pylint: disable=C0103
        if len(self.newrules[nt]) > 1:
            rule = self.ambiguity(self.newrules[nt])
        else:
            rule = self.newrules[nt][0]

        rhs = rule[1]
        attr = [None] * len(rhs)

        for i in range(len(rhs) - 1, -1, -1):
            attr[i] = self.deriveEpsilon(rhs[i])
        return self.rule2func[self.new2old[rule]](attr)

    def buildTree(self, nt, item, tokens, k):  # pylint: disable=C0103
        state, _ = item

        choices = []
        for rule in self.states[state].complete:
            if rule[0] == nt:
                choices.append(rule)
        rule = choices[0]
        if len(choices) > 1:
            rule = self.ambiguity(choices)

        rhs = rule[1]
        attr = [None] * len(rhs)

        for i in range(len(rhs) - 1, -1, -1):
            sym = rhs[i]
            if sym not in self.newrules:
                if sym != self._BOF:
                    attr[i] = tokens[k - 1]
                    key = (item, k)
                    item, k = self.predecessor(key, None)
            # elif self.isnullable(sym):
            elif self._NULLABLE == sym[0 : len(self._NULLABLE)]:
                attr[i] = self.deriveEpsilon(sym)
            else:
                key = (item, k)
                why = self.causal(key)
                attr[i] = self.buildTree(sym, why[0], tokens, why[1])
                item, k = self.predecessor(key, why)
        return self.rule2func[self.new2old[rule]](attr)

    def ambiguity(self, rules):
        #
        #  FIX ME - problem here and in collectRules() if the same rule
        #           appears in >1 method.  Also undefined results if rules
        #           causing the ambiguity appear in the same method.
        #
        sortlist = []
        name2index = {}
        for i, rule in enumerate(rules):
            _, rhs = rule = rule
            name = self.rule2name[self.new2old[rule]]
            sortlist.append((len(rhs), name))
            name2index[name] = i
        sortlist.sort()
        result_list = [name for _, name in sortlist]
        return rules[name2index[self.resolve(result_list)]]

    @staticmethod
    def resolve(input_list):
        #
        #  Resolve ambiguity in favor of the shortest RHS.
        #  Since we walk the tree from the top down, this
        #  should effectively resolve in favor of a "shift".
        #
        return input_list[0]


#
#  GenericASTBuilder automagically constructs a concrete/abstract syntax tree
#  for a given input.  The extra argument is a class (not an instance!)
#  which supports the "__setslice__" and "__len__" methods.
#
#  FIX ME - silently overrides any user code in methods.
#


class GenericASTBuilder(GenericParser):
    def __init__(self, AST, start):
        GenericParser.__init__(self, start)
        self.ast = AST

    def preprocess(self, rule, func):  # pylint: disable=W0221
        # pylint: disable=C3001
        rebind = (
            lambda lhs, self=self: lambda args, lhs=lhs, self=self: self.buildASTNode(
                args, lhs
            )
        )
        lhs, _ = rule
        return rule, rebind(lhs)

    def buildASTNode(self, args, lhs):  # pylint: disable=C0103
        children = []
        for arg in args:
            if isinstance(arg, self.ast):
                children.append(arg)
            else:
                children.append(self.terminal(arg))
        return self.nonterminal(lhs, children)

    @staticmethod
    def terminal(token):
        return token

    def nonterminal(self, token_type, args):
        rv = self.ast(token_type)
        rv[: len(args)] = args
        return rv


#
#  GenericASTTraversal is a Visitor pattern according to Design Patterns.  For
#  each node it attempts to invoke the method n_<node type>, falling
#  back onto the default() method if the n_* can't be found.  The preorder
#  traversal also looks for an exit hook named n_<node type>_exit (no default
#  routine is called if it's not found).  To prematurely halt traversal
#  of a subtree, call the prune() method -- this only makes sense for a
#  preorder traversal.  Node type is determined via the typestring() method.
#


class GenericASTTraversalPruningException(Exception):
    pass


class GenericASTTraversal:
    def __init__(self, ast):
        self.ast = ast

    @staticmethod
    def typestring(node):
        return node.type

    @staticmethod
    def prune():
        raise GenericASTTraversalPruningException

    def preorder(self, node=None):
        if node is None:
            node = self.ast

        try:
            name = "n_" + self.typestring(node)
            if hasattr(self, name):
                func = getattr(self, name)
                func(node)
            else:
                self.default(node)
        except GenericASTTraversalPruningException:
            return

        for kid in node:
            self.preorder(kid)

        name = name + "_exit"
        if hasattr(self, name):
            func = getattr(self, name)
            func(node)

    def postorder(self, node=None):
        if node is None:
            node = self.ast

        for kid in node:
            self.postorder(kid)

        name = "n_" + self.typestring(node)
        if hasattr(self, name):
            func = getattr(self, name)
            func(node)
        else:
            self.default(node)

    def default(self, node):
        pass


#
#  GenericASTMatcher.  AST nodes must have "__getitem__" and "__cmp__"
#  implemented.
#
#  FIX ME - makes assumptions about how GenericParser walks the parse tree.
#


class GenericASTMatcher(GenericParser):
    def __init__(self, start, ast):
        GenericParser.__init__(self, start)
        self.ast = ast

    def preprocess(self, rule, func):  # pylint: disable=W0221
        # pylint: disable=C3001
        rebind = (
            lambda func, self=self: lambda args, func=func, self=self: self.foundMatch(
                args, func
            )
        )
        lhs, rhs = rule
        rhslist = list(rhs)
        rhslist.reverse()

        return (lhs, tuple(rhslist)), rebind(func)

    @staticmethod
    def foundMatch(args, func):  # pylint: disable=C0103
        func(args[-1])
        return args[-1]

    def match_r(self, node):
        self.input.insert(0, node)
        children = 0

        for child in node:
            if not children:
                self.input.insert(0, "(")
            children += 1
            self.match_r(child)

        if children > 0:
            self.input.insert(0, ")")

    def match(self, ast=None):
        if ast is None:
            ast = self.ast
        self.input = []  # pylint: disable=W0201

        self.match_r(ast)
        self.parse(self.input)

    def resolve(self, input_list):  # pylint: disable=W0221
        #
        #  Resolve ambiguity in favor of the longest RHS.
        #
        return input_list[-1]
