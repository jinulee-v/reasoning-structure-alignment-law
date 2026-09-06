/* -------------  Statutory rules ------------- */

/* flight region : Beijing (China) <-> Sacramento (U.S.)               */
region(china_usa).

/* William's booking class                                              */
class(main_plus).

/* Main-Plus allowance - first 2 checked bags are free (0 fee)          */
checked_bag_fee(Pos, 0) :-
    class(main_plus),
    Pos =< 2, !.
checked_bag_fee(Pos, 200) :-                % 3rd bag and onwards (to / from China)
    class(main_plus),
    Pos  > 2,
    region(china_usa).

/* ------------  Weight surcharges (to / from China) ------------------ */
overweight_fee(W, 0)  :- W =< 50, !.
overweight_fee(W, 30) :- W  > 50, W =< 53, !.
overweight_fee(W, 100):- W > 53, W =< 70, !.
overweight_fee(W, 450):- W > 70, W =< 100, !.

/* -------------  Size surcharges (to / from China) ------------------- */
oversize_fee(S, 0)   :- S =< 62, !.
oversize_fee(S, 30)  :- S  > 62, S =< 65, !.
oversize_fee(S, 200) :- S  > 65, S =< 115, !.

/* higher of oversize vs overweight applies (in addition to bag fee)   */
extra_fee(BagId, Extra) :-
    bag(BagId, L, W, H, Weight, yes),        % checked bag only
    S is L + W + H,
    oversize_fee(S, OS),
    overweight_fee(Weight, OW),
    ( OS >= OW -> Extra = OS ; Extra = OW ).

/* -------------  Facts from William's case --------------------------- */

/* carry-on (not checked) */
bag(b1,22,14,9, 9,  no).   % fits carry-on limits, no fee

/* checked bags (order in which they'll be processed) */
bag(b2,33,18,14,90, yes).  % #1
bag(b3,38,15,12,72, yes).  % #2
bag(b4,38,13,14,93, yes).  % #3
bag(b5,46,30,19,83, yes).  % #4
bag(b6,34,16,13,53, yes).  % #5
bag(b7,38,17, 9,52, yes).  % #6
bag(b8,42,22,19,53, yes).  % #7

/* position of each checked bag                                        */
bag_order(b2,1).
bag_order(b3,2).
bag_order(b4,3).
bag_order(b5,4).
bag_order(b6,5).
bag_order(b7,6).
bag_order(b8,7).

/* ------------  Total bag cost --------------------------------------- */
bag_total_fee(BagId, Total) :-
    bag_order(BagId, Pos),
    checked_bag_fee(Pos, BagFee),
    extra_fee(BagId, Extra),
    Total is BagFee + Extra.

total_bag_fees(Sum) :-
    findall(F, bag_total_fee(_,F), Fs),
    sum_list(Fs, Sum).

/* ------------  Ticket price ----------------------------------------- */
ticket_price(585).

/* ------------  Grand total ------------------------------------------ */
total_cost(Total) :-
    total_bag_fees(BagSum),
    ticket_price(Ticket),
    Total is Ticket + BagSum.

/* -------------------------------------------------------------------- */
:- total_cost(T), format('Total cost: ~w~n', [T]).
:- halt.