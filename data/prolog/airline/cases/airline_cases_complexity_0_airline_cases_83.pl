/* ------  Statutory rules relevant to this case  ------ */

/* Carry-on size limits */
carry_on_limit(22,14,9).

/* Base checked-bag fees for trips within / between the U.S. and Canada - Main Cabin */
base_fee(1,35).          /* 1st checked bag            */
base_fee(2,45).          /* 2nd checked bag            */
base_fee(3,150).         /* 3rd checked bag            */
base_fee(N,200) :- N>=4. /* 4th bag and every bag 4+   */

/* Over-size fees for the U.S. / Canada market */
oversize_fee(Dim,30) :-  Dim>62 , Dim=<65.
oversize_fee(Dim,200) :- Dim>65 , Dim=<115.
oversize_fee(Dim,0)  :-  Dim=<62.

/* Over-weight fees for the U.S. / Canada market */
overweight_fee(W,30)  :-  W>50 , W=<53.
overweight_fee(W,100) :-  W>53 , W=<70.
overweight_fee(W,200) :-  W>70 , W=<100.
overweight_fee(W,0)   :-  W=<50.

/* Surcharge for a bag is the higher of its over-size or over-weight fee */
surcharge(Dim,Weight,Fee) :-
    oversize_fee(Dim,OF),
    overweight_fee(Weight,WF),
    Fee is max(OF,WF).

/* ------  Facts for Joseph's journey  ------ */

/* flight ticket price */
ticket_cost(260).

/* Bags:  bag(ID,Length,Width,Height,Weight). */
bag(1,21,14, 8,11).
bag(2,35,21, 9,58).
bag(3,36,13,14,84).
bag(4,43,31,18,52).
bag(5,39,22,14,76).

/* ------  Derived facts  ------ */

/* carry_on_bag/1 : true if the bag fits carry-on limits */
carry_on_bag(ID) :-
    bag(ID,L,W,H,_),
    carry_on_limit(MaxL,MaxW,MaxH),
    L =< MaxL, W =< MaxW, H =< MaxH.

/* checked_bag/2 : checked_bag(ID,Position) - assigns order 1,2,3,... */
checked_bag(ID,Pos) :-
    findall(B,(bag(B,_,_,_,_),\+carry_on_bag(B)),Bs),
    nth1(Pos,Bs,ID).

/* fee_for_bag/2 : fee_for_bag(BagID,TotalFeeForThatBag) */
fee_for_bag(ID,Fee) :-
    checked_bag(ID,Pos),
    base_fee(Pos,Base),
    bag(ID,L,W,H,Wt),
    Dim is L+W+H,
    surcharge(Dim,Wt,Sur),
    Fee is Base+Sur.

/* Sum of all checked-bag fees */
checked_bags_total(Total) :-
    findall(F,fee_for_bag(_,F),Fs),
    sumlist(Fs,Total).

/* ------  Final total cost  ------ */
total_cost(Total) :-
    ticket_cost(Ticket),
    checked_bags_total(BagFees),
    Total is Ticket+BagFees.

/* ------  Query & output  ------ */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.