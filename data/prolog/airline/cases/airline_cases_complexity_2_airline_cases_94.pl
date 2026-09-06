/* ---------- Rules from the statutes that matter for this case ---------- */

/* Checked-bag base fee for Basic-Economy itineraries between Europe and the U.S.
   1st bag $75, 2nd bag $100, 3rd bag and each additional bag $200                */
base_checked_fee(1,75).
base_checked_fee(2,100).
base_checked_fee(N,200) :- N>=3.

/* Over-WEIGHT fee, Europe<->US (all cabins share the same numbers) */
overweight_fee(Weight,Fee) :-
    Weight =< 50, Fee = 0.                       /* not overweight            */
overweight_fee(Weight,30) :-
    Weight  > 50, Weight =< 53.                  /* 50-53 lbs                 */
overweight_fee(Weight,100) :-
    Weight  > 53, Weight =< 70.                  /* 53-70 lbs                 */
overweight_fee(Weight,_) :-
    Weight  > 70, !, fail.                       /* >70 lbs - not accepted    */

/* Over-SIZE fee, Europe<->US (all cabins) */
oversize_fee(DimSum,0) :- DimSum =< 62.          /* within size allowance     */
oversize_fee(DimSum,30) :-
    DimSum  > 62, DimSum =< 65.                  /* 62-65 in                  */
oversize_fee(DimSum,150) :-
    DimSum  > 65, DimSum =< 115.                 /* 65-115 in                 */
oversize_fee(DimSum,_) :-
    DimSum  > 115, !, fail.                      /* >115 in - not accepted    */

/* For a bag that is both over-weight and over-size, the higher of the 2 fees
   applies (in addition to the base checked-bag fee).                          */
extra_fee(Weight,DimSum,Fee) :-
    overweight_fee(Weight,OW), oversize_fee(DimSum,OS),
    Fee is max(OW,OS).

/* ---------- Facts for Sarah's flight and luggage ---------- */

flight_ticket_cost(289).

/* Sarah carries 11 items.  Item #1 is used as the free carry-on,
   therefore items #2 - #11 are the checked bags (10 bags).               */
bag( 1, 21,12, 8, 12).    /* carry-on (free) */

bag( 2, 38,17,16, 60).
bag( 3, 36,20, 9, 51).
bag( 4, 45,31,20, 57).
bag( 5, 35,20, 9, 53).
bag( 6, 39,19,11, 57).
bag( 7, 51,29,22, 52).
bag( 8, 46,33,23, 64).
bag( 9, 48,28,26, 52).
bag(10, 49,33,26, 52).
bag(11, 37,15,13, 53).

/* ---------- Helper predicates ---------- */

/* list of checked bag item numbers (everything except #1) */
checked_bag_numbers(BagNums) :-
    findall(N, (bag(N,_,_,_,_), N \= 1), BagNums).

/* total cost of all checked bags (base + extra) */
checked_bags_total_cost(Total) :-
    checked_bag_numbers(Ns),
    checked_bags_total_cost(Ns,1,0,Total).

checked_bags_total_cost([],_,Acc,Acc).
checked_bags_total_cost([N|Rest],Order,Acc,Total) :-
    bag(N,L,W,H,Weight),
    DimSum is L+W+H,
    base_checked_fee(Order,BaseFee),
    extra_fee(Weight,DimSum,ExtraFee),
    BagFee is BaseFee + ExtraFee,
    NextOrder is Order + 1,
    NewAcc is Acc + BagFee,
    checked_bags_total_cost(Rest,NextOrder,NewAcc,Total).

/* ---------- Final total (ticket + bags) ---------- */
total_cost(Total) :-
    flight_ticket_cost(Ticket),
    checked_bags_total_cost(BagsCost),
    Total is Ticket + BagsCost.

/* ---------- Query to print the answer ---------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.