/* --------------  Statutory rules -------------- */

% passenger information
class(main_plus).
route(us_canada).                      % Minneapolis - Ottawa
ticket_price(123).

% how many checked bags are free with the fare
free_checked_bags(main_plus,1).

/* ---- base checked-bag fee for the route (within / between U.S. & Canada) ---- */
base_checked_fee(BagNumber, Fee) :-
    class(Class),
    free_checked_bags(Class, Free),
    BagNumber =< Free,                         % the complimentary bag(s)
    Fee = 0.

base_checked_fee(BagNumber, 45)  :- BagNumber > 1, BagNumber = 2.
base_checked_fee(BagNumber,150)  :- BagNumber = 3.
base_checked_fee(BagNumber,200)  :- BagNumber >= 4.

/* ---- overweight fee (within / between U.S. & Canada) ---- */
overweight_fee(W,Fee) :-
    W > 70 ,               Fee = 200 , !.
overweight_fee(W,Fee) :-
    W > 53 ,               Fee = 100 , !.
overweight_fee(W,Fee) :-
    W > 50 ,               Fee = 30  , !.
overweight_fee(_,0).

/* ---- oversize fee (within / between U.S. & Canada) ---- */
oversize_fee(DimSum,Fee) :-
    DimSum > 65,           Fee = 200 , !.
oversize_fee(DimSum,Fee) :-
    DimSum > 62,           Fee = 30  ,  !.
oversize_fee(_,0).

/* ---- checked-bag total fee (base + max(overweight,oversize)) ---- */
bag_total_fee(BagNumber, DimSum, Weight, TotalFee) :-
    base_checked_fee(BagNumber, Base),
    overweight_fee(Weight, OFee),
    oversize_fee(DimSum, SFee),
    MaxExtra is max(OFee, SFee),
    TotalFee is Base + MaxExtra.

/* --------------  Case facts -------------- */

% carry-on item (counts as the 1 free carry-on, so not checked, no fee)
carry_on(bag1,21,11,9,9).

% checked items: bag(ID,Length,Width,Height,Weight).
bag(bag2,35,21, 9, 86).
bag(bag3,41,26,22, 65).
bag(bag4,41,18,15, 57).
bag(bag5,35,20,10, 93).
bag(bag6,53,30,31, 68).
bag(bag7,33,19,12, 52).
bag(bag8,41,24,15, 69).

/* --------------  Computing the answer -------------- */

% produce an ordered list of the 7 checked bags
checked_bag_list([bag2,bag3,bag4,bag5,bag6,bag7,bag8]).

% compute fees for every checked bag in order 1..N
checked_bag_fee_list([],_,[]).
checked_bag_fee_list([BagID|Rest],Num,[Fee|Fees]) :-
    bag(BagID,L,W,H,Weight),
    DimSum is L+W+H,
    bag_total_fee(Num,DimSum,Weight,Fee),
    NextNum is Num+1,
    checked_bag_fee_list(Rest,NextNum,Fees).

% total of all checked-bag fees
total_checked_fees(Total) :-
    checked_bag_list(Bags),
    checked_bag_fee_list(Bags,1,Fees),
    sumlist(Fees,Total).

% grand total = ticket + checked-bag fees
total_cost(Grand) :-
    ticket_price(P),
    total_checked_fees(BagFees),
    Grand is P + BagFees.

/* --------------  Query -------------- */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.