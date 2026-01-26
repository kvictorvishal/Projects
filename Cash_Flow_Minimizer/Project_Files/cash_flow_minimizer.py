class CashFlowMinimizer:
    def __init__(self, names):
        self.names = names
        self.id = {n:i for i,n in enumerate(names)}

    def compute(self, tx):
        net = [0]*len(self.names)
        for d,c,a in tx:
            net[self.id[d]] -= a
            net[self.id[c]] += a
        return net

    def minimize(self, net):
        res=[]
        while True:
            d=min(range(len(net)), key=lambda i: net[i])
            c=max(range(len(net)), key=lambda i: net[i])
            if net[d]>=0 or net[c]<=0: break
            amt=min(-net[d],net[c])
            res.append((self.names[d],self.names[c],amt))
            net[d]+=amt; net[c]-=amt
        return res
