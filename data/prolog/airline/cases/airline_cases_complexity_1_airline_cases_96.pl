/* ----------  Statutory rules we need for this case  ---------- */

/* Carry-on limits */
carryon_limits(22,14,9).

/* Business Class - checked-bag base fees on a flight between South America
   (Ecuador) and the U.S.:
      1st and 2nd bag : $0
      3rd bag onward  : $200                                               */
base_checked_fee(Index,0)  :- Index =:= 1 ; Index =:= 2.
base_checked_fee(Index,200):- Index  >  2.

/* Oversize fees on the route South America <-> U.S.                       */
oversize_fee(Dim,0)   :- Dim =< 62.
oversize_fee(Dim,30)  :- Dim  > 62, Dim =< 65.
oversize_fee(Dim,150) :- Dim  > 65, Dim =< 115.

/* Overweight fees on the route South America <-> U.S.                     */
overweight_fee(W,0)   :- W =< 50.
overweight_fee(W,30)  :- W  > 50, W =< 53.
overweight_fee(W,100) :- W  > 53, W =< 70.
overweight_fee(W,200) :- W  > 70, W =< 100.

/* For a checked bag, the 'extra' fee is the higher of oversize vs. overweight */
extra_fee(Dim,W,Fee) :-
    oversize_fee(Dim,OS),
    overweight_fee(W,OW),
    ( OS >= OW -> Fee = OS ; Fee = OW).

/* ----------------  Facts from the specific case  --------------------- */

flight_ticket(575).              /* $575 ticket price */

bag(1,19,11,8, 7).               /* id, L, W, H, Weight (lbs) */
bag(2,47,22,23,65).
bag(3,50,27,23,81).
bag(4,42,27,17,53).
bag(5,37,13,14,91).
bag(6,41,25,21,53).
bag(7,54,32,27,55).
bag(8,36,17,10,79).

/* ----------------  Derived facts  ------------------------------------ */

/* Which bag is carry-on? */
carryon(Id) :-
    bag(Id,L,W,H,_),
    carryon_limits(MaxL,MaxW,MaxH),
    L =< MaxL, W =< MaxW, H =< MaxH.

/* Checked bags in the order they will be counted (ascending id here) */
checked_list(Checked) :-
    findall(Id,(bag(Id,_,_,_,_), \+ carryon(Id)),Checked).

/* Index (1-based) that a checked bag has in the sequence of checked bags */
bag_index(Id,Index) :-
    checked_list(List),
    nth1(Index,List,Id).

/* Cost of one checked bag (base fee + highest of oversize / overweight) */
checked_bag_cost(Id,Total) :-
    bag_index(Id,Idx),
    base_checked_fee(Idx,Base),
    bag(Id,L,W,H,Weight),
    Dim is L+W+H,
    extra_fee(Dim,Weight,Extra),
    Total is Base + Extra.

/* Sum of all checked-bag costs */
checked_bags_total(Cost) :-
    findall(T, (bag(Index,_,_,_,_), \+ carryon(Index), checked_bag_cost(Index,T)), Ts),
    sumlist(Ts,Cost).

/* ----------------  Overall total ------------------------------------- */
total_cost(Total) :-
    flight_ticket(Tix),
    checked_bags_total(Bags),
    Total is Tix + Bags.

/* ----------------  Query / output ------------------------------------ */
:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.