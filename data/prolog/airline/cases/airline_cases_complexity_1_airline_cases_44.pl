/* ----------  GENERAL RULES  ---------- */

% maximum of 2 numbers
max(A,B,A) :- A>=B, !.
max(_,B,B).

/* ---- checked-bag base fee (Premium Economy, domestic flight) ----
   1st-2nd bag : $0
   3rd bag     : $150
   4th+ bag    : $200
*/
base_fee(Ordinal,0)   :- Ordinal =< 2, !.
base_fee(3,150)       :- !.
base_fee(Ordinal,200) :- Ordinal >= 4.

/* ---- overweight fees (domestic) ---- */
overweight_fee(W,200) :- W>70,  W=<100, !.
overweight_fee(W,100) :- W>53,  W=<70,  !.
overweight_fee(W,30)  :- W>50,  W=<53,  !.
overweight_fee(_,0).

/* ---- oversize fees (domestic) ---- */
oversize_fee(S,200) :- S>65,  S=<115, !.
oversize_fee(S,30)  :- S>62,  S=<65,  !.
oversize_fee(_,0).

/* ---- total fee for a single checked bag ---- */
bag_total_fee(Ord,W,S,Total) :-
    base_fee(Ord,Base),
    overweight_fee(W,OW),
    oversize_fee(S,OS),
    max(OW,OS,Extra),          % only the higher of the 2 applies
    Total is Base + Extra.

/* ----------  CASE FACTS  ---------- */

ticket_cost(43).

/* checked bags in the order they'll be processed                */
/* bag(Ordinal, Weight(lbs), Size(in = L+W+H))                    */
bag(1,69,95).
bag(2,74,65).
bag(3,86,65).
bag(4,64,63).
bag(5,60,89).
bag(6,98,107).
bag(7,96,93).

/* ----------  AGGREGATION  ---------- */

sum_list([],0).
sum_list([H|T],Sum) :- sum_list(T,R), Sum is H+R.

total_bag_cost(Total) :-
    findall(Fee,(bag(O,W,S),bag_total_fee(O,W,S,Fee)),Fees),
    sum_list(Fees,Total).

total_cost(Total) :-
    ticket_cost(Ticket),
    total_bag_cost(Bags),
    Total is Ticket + Bags.

/* ----------  QUERY  ---------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.