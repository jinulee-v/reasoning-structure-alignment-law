/* ----------  Statutory rules relevant to this case  ---------- */

% overweight fees for a Basic Economy passenger travelling China -> U.S.
overweight_fee(Weight, 450) :- Weight > 70, !.
overweight_fee(Weight, 100) :- Weight > 53, !.
overweight_fee(Weight,  30) :- Weight > 50, !.
overweight_fee(_,              0).

% oversize fees China -> U.S.
oversize_fee(Size, 200) :- Size > 65, !.          % up to 115 in.
oversize_fee(Size,  30) :- Size > 62, !.          % 62 - 65 in.
oversize_fee(_,        0).

% choose the higher of the 2 surcharges
extra_fee(Weight,Size,Fee) :-
        overweight_fee(Weight,OW),
        oversize_fee(Size,OS),
        ( OW >= OS -> Fee = OW ; Fee = OS ).

% base checked-bag fee number N (Basic Economy ; China -> U.S.)
base_fee(1,  75).
base_fee(2, 100).
base_fee(N, 200) :- N >= 3.

/* ----------  Facts describing Linda's trip  ---------- */

ticket_cost(1124).

% bag(ID, Length, Width, Height, Weight).
bag(1, 20,11, 6, 10).      % free carry-on (ignored for fees)
bag(2, 55,32,27, 53).
bag(3, 33,21,10, 51).
bag(4, 37,15,12, 76).
bag(5, 37,19,10, 92).
bag(6, 48,35,27, 52).
bag(7, 35,17,11, 53).
bag(8, 47,26,26, 77).
bag(9, 42,22,17, 94).
bag(10,33,18,13, 51).
bag(11,55,29,31, 51).

% order of checked bags (bag 1 is carry-on, so start with 2)
bag_order(2,1).
bag_order(3,2).
bag_order(4,3).
bag_order(5,4).
bag_order(6,5).
bag_order(7,6).
bag_order(8,7).
bag_order(9,8).
bag_order(10,9).
bag_order(11,10).

/* ----------  Helper predicates  ---------- */

linear_size(L,W,H,Size) :- Size is L+W+H.

bag_cost(ID,Cost) :-
        bag_order(ID,Num),
        bag(ID,L,W,H,Weight),
        linear_size(L,W,H,Size),
        extra_fee(Weight,Size,Surcharge),
        base_fee(Num,Base),
        Cost is Base + Surcharge.

sum_list([],0).
sum_list([H|T],Sum) :- sum_list(T,S1), Sum is H+S1.

total_bags_cost(Total) :-
        findall(C, bag_cost(_,C), Cs),
        sum_list(Cs,Total).

total_cost(Total) :-
        ticket_cost(Ticket),
        total_bags_cost(Bags),
        Total is Ticket + Bags.

/* ----------  Query & output  ---------- */

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.