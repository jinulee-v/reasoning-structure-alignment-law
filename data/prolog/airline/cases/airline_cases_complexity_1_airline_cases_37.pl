/* ---------- FACTS ---------- */

% ticket
ticket_cost(335).

% William's checked bags (Index, Length, Width, Height, Weight)
bag(1,40,14,16,93).
bag(2,49,27,27,54).
bag(3,37,17,9,60).
bag(4,33,19,11,51).
bag(5,43,27,22,72).
bag(6,38,18,10,59).
bag(7,33,17,14,53).

% William's cabin
class(main_plus).

/* ---------- RULES ---------- */

% free-bag allowance for Main Plus (Main Cabin + 1 extra)
free_bags(2).

/* ---- base bag fee (to / from India, Main Cabin) ---- */
nominal_base_fee(1,0).        % 1st bag
nominal_base_fee(2,100).      % 2nd bag
nominal_base_fee(N,200) :-    % 3rd, 4th, ... bags
    N>=3.

base_fee(Index,0) :-                 % waived if within free allowance
    free_bags(FB), Index =< FB, !.
base_fee(Index,Fee) :-               % otherwise nominal fee applies
    nominal_base_fee(Index,Fee).

/* ---- oversize fee (to / from India) ---- */
oversize_fee(Size,0)    :- Size =< 62, !.
oversize_fee(Size,30)   :- Size =< 65, !.
oversize_fee(Size,200)  :- Size =< 115, !.

/* ---- overweight fee (to / from India) ---- */
overweight_fee(W,0)     :- W =< 50, !.
overweight_fee(W,30)    :- W =< 53, !.
overweight_fee(W,100)   :- W =< 70, !.
overweight_fee(W,450)   :- W =< 100, !.

/* ---- charge for a single bag ---- */
bag_total(Index,L,W,H,Weight,Total) :-
    Size is L+W+H,
    base_fee(Index,Base),
    oversize_fee(Size,OS),
    overweight_fee(Weight,OW),
    ( OS >= OW -> Extra = OS ; Extra = OW ),   % higher of the 2
    Total is Base + Extra.

/* ---- list summation helper ---- */
sum_list([],0).
sum_list([H|T],Sum) :-
    sum_list(T,Rest),
    Sum is Rest + H.

/* ---- overall total ---- */
total_cost(Total) :-
    findall(F, (bag(I,L,W,H,WT), bag_total(I,L,W,H,WT,F)), Fees),
    sum_list(Fees,BagSum),
    ticket_cost(Tkt),
    Total is BagSum + Tkt.

/* ---------- QUERY ---------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.