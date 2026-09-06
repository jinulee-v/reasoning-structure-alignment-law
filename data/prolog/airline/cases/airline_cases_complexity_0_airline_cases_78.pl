/* ---------- Facts describing Daniel's journey ---------- */

% ticket
ticket_cost(579).

% every bag: bag(Id, Length, Width, Height, Weight).
bag(b1,19,11, 9,  8).     % carry-on
bag(b2,48,33,24, 52).     % checked 1
bag(b3,34,16,14, 67).     % checked 2
bag(b4,43,26,17, 77).     % checked 3
bag(b5,49,34,26, 74).     % checked 4

% cabin and route (needed only to pick the right numbers; all numbers
% are hard-coded below for the China<->USA, Main-Cabin case)
cabin(main_cabin).
route(china_to_usa).

/* ---------- General limits (China <-> U.S. flights) ---------- */

carry_on_max(22,14,9).            % =< 22*14*9 in

/* ---------- Helper predicates ---------- */

% is_carry_on/1  - true if BagId meets carry-on size limits
is_carry_on(Bag) :-
    bag(Bag,L,W,H,_),
    carry_on_max(MaxL,MaxW,MaxH),
    L =< MaxL, W =< MaxW, H =< MaxH.

% list of checked bags (everything that is not carry-on)
checked_bag_list(List) :-
    findall(B, (bag(B,_,_,_,_), \+ is_carry_on(B)), List).

% dimensional sum of a bag
dim_sum(B,Sum) :- bag(B,L,W,H,_), Sum is L+W+H.

/* ---------- Over-size / over-weight surcharges (China <-> U.S.) ---------- */

oversize_charge(B,Charge) :-
    dim_sum(B,S),
    ( S > 115                       -> Charge = 1_000_000        % not accepted
    ; S > 65                        -> Charge = 200
    ; S > 62                        -> Charge = 30
    ;                                Charge = 0).

overweight_charge(B,Charge) :-
    bag(B,_,_,_,Wt),
    ( Wt > 100                      -> Charge = 1_000_000        % not accepted
    ; Wt > 70                       -> Charge = 450
    ; Wt > 53                       -> Charge = 100
    ; Wt > 50                       -> Charge = 30
    ;                                Charge = 0).

% final surcharge is the higher of the two
surcharge(B,Charge) :-
    oversize_charge(B,OS),
    overweight_charge(B,OW),
    ( OS >= OW -> Charge = OS ; Charge = OW).

/* ---------- Base checked-bag fees (Main Cabin, China <-> U.S.) ---------- */

base_charge(1,0).          % first bag free
base_charge(2,100).        % second bag
base_charge(I,200) :-      % 3rd, 4th, ... bags
    I >= 3.

/* ---------- Cost of every checked bag ---------- */

bag_costs([], _, []).
bag_costs([B|Rest], Index, [Cost|CRest]) :-
    base_charge(Index,Base),
    surcharge(B,Surch),
    Cost is Base + Surch,
    Next is Index + 1,
    bag_costs(Rest,Next,CRest).

total_bag_cost(Total) :-
    checked_bag_list(Checked),
    bag_costs(Checked,1,Costs),
    sum_list(Costs,Total).

/* ---------- Grand total ---------- */

total_cost(Total) :-
    ticket_cost(Ticket),
    total_bag_cost(Bags),
    Total is Ticket + Bags.

/* ---------- Query ---------- */
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.