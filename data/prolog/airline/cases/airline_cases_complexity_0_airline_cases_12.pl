/* =========================================================
   Statutory rules and facts for Robert's itinerary
   ========================================================= */

/* ----------------  Carry-on limits  ---------------------- */
carry_on_max(22,14,9).          % length, width, height (inches)

/* ----------------  Checked-bag fees (Main Plus) ---------- */
/* Main Plus = Main Cabin allowance + 1 complimentary bag
   (domestic U.S. route; max 2 checked-bag allowance).       */
checked_fee(1, 0).              % 1st checked bag is free
checked_fee(2, 45).             % 2nd checked bag
checked_fee(3,150).             % 3rd checked bag
checked_fee(N,200) :- N>=4.     % 4th bag and beyond

/* ----------------  Extra fees - size --------------------- */
/* Route: within / between U.S. & Canada / PR / USVI         */
oversize_fee(Dim,30)  :- Dim>62 , Dim=<65.
oversize_fee(Dim,200) :- Dim>65 , Dim=<115.
oversize_fee(Dim,0)   :- Dim=<62.

/* ----------------  Extra fees - weight ------------------- */
overweight_fee(W,30)   :- W>50 , W=<53.
overweight_fee(W,100)  :- W>53 , W=<70.
overweight_fee(W,200)  :- W>70 , W=<100.
overweight_fee(W,0)    :- W=<50.

/* ----------------  Extra fee chooser --------------------- */
/* "The higher fee between oversize and overweight applies,
   in addition to the checked-bag fee."                      */
extra_fee(Dim,W,Fee) :-
        oversize_fee(Dim,OS),
        overweight_fee(W,OW),
        (OS>=OW -> Fee = OS ; Fee = OW).

/* ----------------  Trip facts ---------------------------- */
flight_ticket(178).
route(domestic).                % Minneapolis -> New York inside U.S.

/* bag(Id,Length,Width,Height,Weight) */
bag(1,18,11, 8,  7).     % personal item / carry-on
bag(2,36,16,11, 53).
bag(3,38,22,13, 74).
bag(4,42,21,15, 51).
bag(5,36,22,11, 52).

/* ----------------  Helper predicates --------------------- */

/* sum of the three dimensions */
dim_sum(Id,S) :- bag(Id,L,W,H,_), S is L+W+H.

/* true if a bag fits the carry-on size limits               */
carry_on(Id) :-
        bag(Id,L,W,H,_),
        carry_on_max(MaxL,MaxW,MaxH),
        L=<MaxL, W=<MaxW, H=<MaxH.

/* Determine ordinal number (N) of a checked bag, skipping
   the single carry-on / personal item                       */
checked_bag_number(Id,N) :-
        findall(B,(bag(B,_,_,_,_), \+ carry_on(B)), List),
        nth1(N,List,Id).

/* Cost for one checked bag (base fee + highest extra fee)   */
bag_total_fee(Id,Total) :-
        checked_bag_number(Id,N),
        checked_fee(N,Base),
        dim_sum(Id,Dim),
        bag(Id,_,_,_,W),
        extra_fee(Dim,W,Extra),
        Total is Base + Extra.

/* Sum of all checked-bag fees                               */
total_checked_bag_fees(Sum) :-
        findall(F, bag_total_fee(_,F), Fs),
        sum_list(Fs,Sum).

/* ----------------  Grand total --------------------------- */
total_cost(Total) :-
        flight_ticket(Tix),
        total_checked_bag_fees(Bags),
        Total is Tix + Bags.

/* ----------------  Query & output ------------------------ */
compute_total(Cost) :-
        total_cost(Cost).

:- compute_total(Cost), format('Total cost: ~w~n', [Cost]), halt.