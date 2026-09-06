/* ---------- Statutory rules (subset relevant to this case) ---------- */

/* carry-on limits */
carry_on_limits(22,14,9).

/* base checked-bag fees for Business Class - domestic (within U.S.) */
base_fee(Index,0)   :- Index =< 2.          /* 1st & 2nd bags free   */
base_fee(3,150).                         /* 3rd bag               */
base_fee(Index,200) :- Index >= 4.         /* 4th bag and onwards   */

/* oversize fees - domestic */
oversize_fee(Size,0)                    :- Size =< 62.
oversize_fee(Size,30)                   :- Size  > 62, Size =< 65.
oversize_fee(Size,200)                  :- Size  > 65, Size =< 115.

/* overweight fees - domestic */
overweight_fee(W,0)    :- W =< 50.
overweight_fee(W,30)   :- W > 50, W =< 53.
overweight_fee(W,100)  :- W > 53, W =< 70.
overweight_fee(W,200)  :- W > 70, W =< 100.

/* if both oversize and overweight apply, charge only the higher one */
surcharge(Oversize,Overweight,Over) :-
    (Oversize >= Overweight -> Over = Oversize ; Over = Overweight).

/* ---------- Facts for Thomas' trip ---------- */

flight_ticket(200).

/* bag(Id, Length, Width, Height, Weight). */
bag(1,19,13, 9,  5).
bag(2,41,28,19, 53).
bag(3,34,22, 9, 97).
bag(4,42,22,14,100).
bag(5,50,34,30, 81).
bag(6,37,16,15, 51).
bag(7,34,20, 9, 95).
bag(8,37,12,14, 53).

/* ---------- Derived facts and rules ---------- */

/* identify the (single) carry-on - first bag that fits the limits */
carry_on_id(ID) :-
    carry_on_limits(MaxL,MaxW,MaxH),
    bag(ID,L,W,H,_),
    L =< MaxL, W =< MaxW, H =< MaxH, !.

/* checked bags are all others */
checked_bag(ID) :- bag(ID,_,_,_,_), \+ carry_on_id(ID).

/* list of checked-bag IDs in ascending order */
checked_ids(IDs) :- findall(ID,checked_bag(ID),List), sort(List,IDs).

/* position (1-based) of each checked bag */
bag_index(ID,Idx) :-
    checked_ids(IDs),
    nth1(Idx,IDs,ID).

/* linear size of a bag */
size(ID,S) :-
    bag(ID,L,W,H,_),
    S is L+W+H.

/* oversize fee for a bag */
bag_oversize_fee(ID,Fee) :-
    size(ID,S),
    oversize_fee(S,Fee).

/* overweight fee for a bag */
bag_overweight_fee(ID,Fee) :-
    bag(ID,_,_,_,W),
    overweight_fee(W,Fee).

/* surcharge (max of oversize / overweight) */
bag_surcharge(ID,SFee) :-
    bag_oversize_fee(ID,O1),
    bag_overweight_fee(ID,O2),
    surcharge(O1,O2,SFee).

/* total cost for an individual checked bag */
bag_cost(ID,Cost) :-
    bag_index(ID,Idx),
    base_fee(Idx,BF),
    bag_surcharge(ID,SF),
    Cost is BF + SF.

/* total of all checked-bag costs */
total_bag_cost(Total) :-
    findall(C, (checked_bag(ID), bag_cost(ID,C)), Cs),
    sum_list(Cs,Total).

/* grand total: ticket + bags */
total_cost(Total) :-
    flight_ticket(Ticket),
    total_bag_cost(Bags),
    Total is Ticket + Bags.

/* ---------- Query ---------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.