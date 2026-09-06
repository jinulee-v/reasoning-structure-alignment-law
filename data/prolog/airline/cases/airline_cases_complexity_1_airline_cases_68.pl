/* ----------  Statutory rules that apply to this case  ---------- */

/* size in inches, weight in lbs                                            */
/* Jessica's itinerary is San Juan (Puerto Rico) -> Boston (U.S.),           */
/* Basic Economy.  The relevant region is "within / between U.S.,           */
/* Puerto Rico and U.S. Virgin Islands".                                    */

flight_cost(292).          /* price of the ticket */

/* ----------------  Checked-bag facts (ID, L, W, H, Weight)  -------------- */
bag(2,33,22, 9, 52).
bag(3,35,17,11, 88).
bag(4,40,24,20, 51).
bag(5,47,33,22, 77).
bag(6,46,25,23, 95).
bag(7,38,14,12, 61).
bag(8,51,34,30, 55).

/* order in which the bags are counted (1st-checked, 2nd-checked ...) */
bag_order([2,3,4,5,6,7,8]).

/* --------------  Generic rules derived from the statutes  ---------------- */

/* outside dimension */
size(L,W,H,S) :- S is L+W+H.

/* oversize fee (within U.S./P.R./USVI) */
oversize_fee(Size,Fee) :-
    (   Size > 65              -> Fee = 200          % 65-115 in
    ;   Size > 62              -> Fee = 30           % 62-65  in
    ;                            Fee = 0).

/* overweight fee (within U.S./P.R./USVI, Basic Economy) */
overweight_fee(Wt,Fee) :-
    (   Wt > 70                -> Fee = 200          % 70-100 lbs
    ;   Wt > 53                -> Fee = 100          % 53-70  lbs
    ;   Wt > 50                -> Fee = 30           % 50-53  lbs
    ;                            Fee = 0).

/* When both oversize and overweight apply, the higher one is charged */
extra_fee(Size,Weight,Fee) :-
    oversize_fee(Size,OF),
    overweight_fee(Weight,WF),
    (OF >= WF -> Fee = OF ; Fee = WF).

/* position of a bag in the checked-bag sequence */
bag_position(BagID,Pos) :-
    bag_order(List), nth1(Pos,List,BagID).

/* base checked-bag fee for Basic Economy, within U.S./P.R./USVI */
base_fee(Pos,Fee) :-
    (   Pos =:= 1 -> Fee =  40
    ;   Pos =:= 2 -> Fee =  45
    ;   Pos =:= 3 -> Fee = 150
    ;               Fee = 200 ).      % 4th bag and beyond

/* total fee for one bag = base fee + (max oversize/overweight) */
bag_fee(BagID,Fee) :-
    bag(BagID,L,W,H,Weight),
    size(L,W,H,Size),
    extra_fee(Size,Weight,Extra),
    bag_position(BagID,Pos),
    base_fee(Pos,Base),
    Fee is Base + Extra.

/* sum of all checked-bag fees */
total_checked_cost(Total) :-
    bag_order(Order),
    maplist(bag_fee,Order,Fees),
    sumlist(Fees,Total).

/* grand total = ticket + checked-bag charges (no other special costs) */
total_cost(Total) :-
    flight_cost(Ticket),
    total_checked_cost(Bags),
    Total is Ticket + Bags.

/* ---------------------------  Query  ------------------------------------ */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.