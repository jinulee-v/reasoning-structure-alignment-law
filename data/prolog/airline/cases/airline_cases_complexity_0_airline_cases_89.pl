/* ----------  Statutory rules (only the parts needed for this case) ---------- */

% carry-on size limit
carry_on_size(22,14,9).

% base checked-bag fee for a Business Class customer travelling within the U.S.
% (1st & 2nd bags free, 3rd = $150, 4th+ = $200)
base_fee_biz_us(Num,0)   :- Num =< 2, !.
base_fee_biz_us(3,150)   :- !.
base_fee_biz_us(Num,200) :- Num >= 4.

% oversize fees (within U.S.)
oversize_fee(Size,0)                 :- Size =< 62, !.
oversize_fee(Size,30)                :- Size =< 65, !.          % 62-65 in
oversize_fee(Size,200)               :- Size =< 115, !.         % 65-115 in

% overweight fees (within U.S.)
overweight_fee(W,0)    :- W =< 50,  !.
overweight_fee(W,30)   :- W =< 53,  !.        % >50-53 lb
overweight_fee(W,100)  :- W =< 70,  !.        % >53-70 lb
overweight_fee(W,200)  :- W =< 100, !.        % >70-100 lb
% (>100 lb not accepted - not needed here)

% the surcharge applied to a checked bag is the higher of oversize / overweight
surcharge(Size,Weight,S) :-
    oversize_fee(Size,OS),
    overweight_fee(Weight,OW),
    (OS >= OW -> S = OS ; S = OW).

/* ----------  Case facts  ---------- */

% flight details
ticket_price(244).          % USD
cabin_class(business).
route(within_us).           % Orlando - Philadelphia

% each item: bag(Id,Length,Width,Height,Weight).
bag(1,22,14, 9,  9).   % fits carry-on
bag(2,46,33,23, 52).
bag(3,37,16,11, 82).
bag(4,48,36,26, 93).
bag(5,33,21, 9, 93).

/* ----------  Derived facts / rules  ---------- */

% does a bag qualify as the single free carry-on?
carry_on(Id) :-
    carry_on_size(Lmax,Wmax,Hmax),
    bag(Id,L,W,H,_),
    L =< Lmax, W =< Wmax, H =< Hmax.

% list of checked bags (everything that is not the one carry-on)
checked_bag_list(List) :-
    findall(Id,(bag(Id,_,_,_,_), \+ carry_on(Id)),List).

% position (1st,2nd,3rd...) of a checked bag
bag_number(Id,Num) :-
    checked_bag_list(List),
    nth1(Num,List,Id).

% cost of an individual checked bag
bag_cost(Id,Cost) :-
    bag(Id,L,W,H,Weight),
    Size is L+W+H,
    bag_number(Id,Num),
    base_fee_biz_us(Num,Base),
    surcharge(Size,Weight,Surcharge),
    Cost is Base + Surcharge.

% total of all checked-bag fees
total_checked_fees(Total) :-
    findall(C, (bag(Id,_,_,_,_), \+ carry_on(Id), bag_cost(Id,C)), Cs),
    sum_list(Cs,Total).

% grand total (ticket + bags)
total_cost(Total) :-
    ticket_price(T),
    total_checked_fees(BagFees),
    Total is T + BagFees.

/* ----------  Query requested by the assignment ---------- */

:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.