/* ---------------  Rules derived from the statutes (only what we need) --------------- */

% passenger, class and ticket
passenger(david).
class(david, main_plus).
ticket_price(david, 555).

% route category (U.S. -> China)
route(to_from_china).

/* -------- Carry-on test (18 x 14 x 9 or smaller) -------- */
carry_on(L, W, H) :-
    L =< 22, W =< 14, H =< 9.

/* -------- Oversize fee (to / from China) -------- */
oversize_fee(Sum, Fee) :-
    Sum =< 62,               Fee = 0                              ;   % not oversize
    Sum  > 62, Sum =< 65,    Fee = 30                             ;   % 62-65 in
    Sum  > 65, Sum =< 115,   Fee = 200.                               % 65-115 in

/* -------- Overweight fee (to / from China) -------- */
overweight_fee(W, Fee) :-
    W =< 50,                     Fee = 0   ;                      % not overweight
    W  > 50, W =< 53,            Fee = 30  ;                      % 50-53 lbs
    W  > 53, W =< 70,            Fee = 100 ;                      % 53-70 lbs
    W  > 70, W =< 100,           Fee = 450.                       % 70-100 lbs

/* -------- Extra fee for a bag (max of oversize / overweight) -------- */
extra_fee(L, Wd, H, Weight, Fee) :-
    Sum is L + Wd + H,
    oversize_fee(Sum, OSizeFee),
    overweight_fee(Weight, OWeightFee),
    Fee is max(OSizeFee, OWeightFee).

/* -------- Base checked-bag fee for Main Plus (to / from China) -------- */
% Main Plus = Main Cabin + 1 free extra bag (max 2 free)
base_checked_fee(Index, Fee) :-
    Index =< 2,                       Fee = 0  ;      % 1st & 2nd bag free
    Index =:= 3,                      Fee = 200 ;     % 3rd bag
    Index >= 4,                       Fee = 200.      % 4th bag and beyond

/* ---------------  Facts for David's items --------------- */
/*  bag(ID, Length, Width, Height, Weight)  */
bag(1, 18, 14,  9,  6).      % carry-on
bag(2, 33, 19, 12, 51).
bag(3, 38, 13, 14, 82).
bag(4, 33, 22, 10, 96).
bag(5, 54, 32, 25, 62).

/* ---------------  Determine which bags are checked --------------- */
checked_bag_id(ID) :-
    bag(ID, L, W, H, _),
    \+ carry_on(L, W, H),         % not a carry-on
    ID \= 1.                      % bag #1 is the carry-on

/* ---------------  Ordered list of checked bags --------------- */
checked_bag_list(List) :-
    findall(ID, checked_bag_id(ID), Unsorted),
    sort(Unsorted, List).         % ascending order: 2,3,4,5

/* ---------------  Cost for a single checked bag --------------- */
bag_cost(ID, Index, Cost) :-
    bag(ID, L, W, H, WT),
    extra_fee(L, W, H, WT, Extra),
    base_checked_fee(Index, Base),
    Cost is Base + Extra.

/* ---------------  Total baggage cost --------------- */
total_bags_fee(TotalFee) :-
    checked_bag_list(List),
    findall(C,
            (nth1(I, List, ID), bag_cost(ID, I, C)),
            Costs),
    sum_list(Costs, TotalFee).

/* ---------------  Grand total (ticket + bags) --------------- */
total_cost(Total) :-
    ticket_price(david, Ticket),
    total_bags_fee(BagsFee),
    Total is Ticket + BagsFee.

/* ---------------  Produce the answer --------------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.