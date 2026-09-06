/* ------------  Statutory rules that are relevant to this case ------------ */

% route of interest
route(beijing, phoenix, china_usa).

% passenger class
class(main_cabin).

% ticket price
ticket_price(1290).

% ----------------------------------------------------------------------------
% Bag facts  bag(Id, Length, Width, Height, Weight).
% ----------------------------------------------------------------------------
bag(1, 20, 12,  8, 12).
bag(2, 36, 16, 12, 92).
bag(3, 38, 15, 10, 97).
bag(4, 41, 21, 12, 51).
bag(5, 41, 16, 18, 53).
bag(6, 36, 13, 14, 52).
bag(7, 50, 36, 26, 85).
bag(8, 37, 20, 15, 65).

/* ------------  DIMENSION-BASED PREDICATES --------------------------------- */

size_total(Id, Total) :-
    bag(Id, L, W, H, _),
    Total is L + W + H.

carry_on(Id) :-            % qualifies as a carry-on
    bag(Id, L, W, H, _),
    L =< 22, W =< 14, H =< 9.

/* ------------  BASE CHECKED-BAG FEES  ------------------------------------- */
/*  Beijing <-> USA, Main Cabin
    - 1st checked bag:   $0   (complimentary - "to/from China" rule)
    - 2nd checked bag:  $100
    - 3rd & later :     $200                                   */

base_checked_fee(Pos, 0)   :- Pos =:= 1.      % first checked bag
base_checked_fee(Pos, 100) :- Pos =:= 2.      % second checked bag
base_checked_fee(Pos, 200) :- Pos >= 3.       % third or later

/* ------------  SURCHARGES (oversize / overweight)  ------------------------ */

/* overweight fees (Beijing <-> USA) */
overweight_fee(W, 0)   :- W =< 50.
overweight_fee(W, 30)  :- W  > 50, W =< 53.
overweight_fee(W, 100) :- W  > 53, W =< 70.
overweight_fee(W, 450) :- W  > 70, W =< 100.

/* oversize fees (Beijing <-> USA) */
oversize_fee(S, 0)   :- S =< 62.
oversize_fee(S, 30)  :- S  > 62, S =< 65.
oversize_fee(S, 200) :- S  > 65, S =< 115.

/* Highest of the two applies (never add both) */
surcharge(Id, Charge) :-
    bag(Id, _, _, _, W),
    size_total(Id, S),
    overweight_fee(W, OW),
    oversize_fee(S,  OS),
    ( OW >= OS -> Charge = OW ; Charge = OS ).

/* ------------  WHICH BAGS ARE CHECKED? ------------------------------------ */

checked_bag_list(Checked) :-
    findall(Id, (bag(Id,_,_,_,_), \+ carry_on(Id)), Checked).

/* ------------  COST PER CHECKED BAG --------------------------------------- */

checked_bag_cost(Id, Pos, Cost) :-
    base_checked_fee(Pos, Base),
    surcharge(Id, Surch),
    Cost is Base + Surch.

/* ------------  TOTAL BAG FEES --------------------------------------------- */

total_bag_fees(Total) :-
    checked_bag_list(Checked),
    findall(Cost,
            ( nth1(Pos, Checked, Id),
              checked_bag_cost(Id, Pos, Cost)
            ),
            Costs),
    sum_list(Costs, Total).

/* ------------  OVERALL TOTAL ---------------------------------------------- */

total_cost(Total) :-
    ticket_price(Tix),
    total_bag_fees(BagFees),
    Total is Tix + BagFees.

/* ------------  QUERY ------------------------------------------------------ */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.