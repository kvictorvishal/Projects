#  Cash Flow Minimizer –  Project 

[![Python](https://img.shields.io/badge/Python-3.6%2B-blue.svg)](https://www.python.org/)
[![C++](https://img.shields.io/badge/C%2B%2B-11%2B-brightgreen.svg)](https://isocpp.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

##  Submission
**Category:** Data Structures & Algorithms  
**Problem Type:** Financial Optimization / Expense Splitting  
**Institution:** NITK Surathkal  

---

##  Project Overview

**Cash Flow Minimizer** is a debt optimization system that minimizes the number of transactions required to settle expenses among a group of people.

Instead of executing every individual payment, the algorithm intelligently merges debts so that each participant performs the minimum number of payments while ensuring all balances are settled exactly.

---

##  Problem Statement

Given multiple people with interconnected debts and credits, determine the **minimum number of transactions** required to settle all balances.

###  Naive Approach
- Execute all original transactions
- Leads to redundant payments

###  Optimized Approach
- Compute net balance for each person
- Match largest debtor with largest creditor
- Reduce transactions drastically

---

##  Algorithm – Greedy Debt Matching

1. Compute net balance:
   - Debtor → negative balance
   - Creditor → positive balance

2. While unsettled balances exist:
   - Pick max debtor
   - Pick max creditor
   - Transfer minimum possible amount
   - Update balances

**Time Complexity:** O(N²)  
**Space Complexity:** O(N)

---

##  Example

### Input
```
A → B : 500
A → C : 100
D → B : 200
C → D : 300
```

### Net Balances
```
A : -600
B : +700
C : -200
D : +100
```

### Optimized Transactions
```
A → B : 600
C → B : 100
C → D : 100
```

---

##  Python Implementation

```python
class CashFlowMinimizer:
    def __init__(self, names):
        self.names = names
        self.id = {name: i for i, name in enumerate(names)}

    def compute_net(self, transactions):
        net = [0] * len(self.names)
        for d, c, a in transactions:
            net[self.id[d]] -= a
            net[self.id[c]] += a
        return net

    def minimize(self, net):
        res = []
        while True:
            d = min(range(len(net)), key=lambda i: net[i])
            c = max(range(len(net)), key=lambda i: net[i])
            if net[d] >= 0 or net[c] <= 0:
                break
            amt = min(-net[d], net[c])
            res.append((self.names[d], self.names[c], amt))
            net[d] += amt
            net[c] -= amt
        return res
```

---

##  C++ Implementation

```cpp
#include <bits/stdc++.h>
using namespace std;

class CashFlowMinimizer {
    vector<string> names;
    unordered_map<string,int> id;

public:
    CashFlowMinimizer(vector<string>& n): names(n) {
        for(int i=0;i<n.size();i++) id[n[i]] = i;
    }

    vector<double> compute(vector<tuple<string,string,double>>& t) {
        vector<double> net(names.size(),0);
        for(auto& [d,c,a]:t){
            net[id[d]] -= a;
            net[id[c]] += a;
        }
        return net;
    }

    vector<tuple<string,string,double>> minimize(vector<double>& net) {
        vector<tuple<string,string,double>> res;
        while(true){
            int d = min_element(net.begin(), net.end()) - net.begin();
            int c = max_element(net.begin(), net.end()) - net.begin();
            if(net[d] >= 0 || net[c] <= 0) break;
            double amt = min(-net[d], net[c]);
            res.push_back({names[d], names[c], amt});
            net[d] += amt;
            net[c] -= amt;
        }
        return res;
    }
};
```

---

##  Future Enhancements
- Payment mode compatibility
- Web UI integration
- Database support
- Graph visualization

---

##  License
MIT License  
© 2026 – Hackathon Project, NITK Surathkal
