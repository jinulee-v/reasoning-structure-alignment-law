% ------------ Facts describing the passenger, trip and his items -----------------
% passenger(Class, From, To, TicketPrice).
passenger(basic_economy, phoenix, miami, 287).

% item(Id, Length, Width, Height, Weight).
item(1, 22, 14,  6, 12).
item(2, 33, 17, 14, 58).
item(3, 40, 22, 12, 52).
item(4, 53, 32, 25, 99).
item(5, 37, 12, 14, 86).
item(6, 35, 19,  9, 63).
item(7, 34, 16, 14, 51).
item(8, 37, 16, 10, 97).
item(9, 38, 17, 10, 98).
item(10,34, 19, 12, 66).
item(11,35, 19, 10, 78).

% ------------------------ Utility predicates --------------------------------------
dimsum(L,W,H,Sum) :- Sum is L+W+H.

% 1 carry-on allowed if dimensions =< 22x14x9
carry_on_candidate(Id) :-
    item(Id,L,W,H,_),
    L =< 22, W =< 14, H =< 9.

% choose the 1st item that fits as the carry-on
carry_on_id(Id) :- once(carry_on_candidate(Id)).

% ------------------- Checked-bag base fees (within U.S.) --------------------------
base_checked_fee(N,40) :- N =:= 1.           % 1st bag
base_checked_fee(N,45) :- N =:= 2.           % 2nd bag
base_checked_fee(N,150):- N =:= 3.           % 3rd bag
base_checked_fee(N,200):- N >= 4.            % 4th bag +

% ------------------ Oversize / Over-weight surcharges ----------------------------
oversize_fee(DimSum,Fee) :-
    ( DimSum =< 62 -> Fee = 0
    ; DimSum =< 65 -> Fee = 30
    ; DimSum =<115 -> Fee = 200
    ;                  Fee = 99999  % (not needed here)
    ).

overweight_fee(Wt,Fee) :-
    ( Wt =< 50  -> Fee = 0
    ; Wt =< 53  -> Fee = 30
    ; Wt =< 70  -> Fee = 100
    ; Wt =< 100 -> Fee = 200
    ;              Fee = 99999     % (>100 not accepted; not needed here)
    ).

surcharge(L,W,H,Wt,S) :-
    dimsum(L,W,H,D),
    oversize_fee(D,OF),
    overweight_fee(Wt,WF),
    (OF >= WF -> S = OF ; S = WF).

% ------------------- Calculation for every checked bag ---------------------------
bag_total_cost(Index, Id, Cost) :-
    item(Id,L,W,H,Wt),
    base_checked_fee(Index,Base),
    surcharge(L,W,H,Wt,S),
    Cost is Base + S.

% --------------- Compute aggregate of all checked items --------------------------
compute_checked([],_,Acc,Acc).
compute_checked([Id|Rest],Idx,Acc,Total) :-
    bag_total_cost(Idx,Id,C),
    Idx1 is Idx+1,
    Acc1 is Acc + C,
    compute_checked(Rest,Idx1,Acc1,Total).

% ------------------------- Overall total -----------------------------------------
ticket_fee(Fee) :- passenger(_,_,_,Fee).

total_cost(Total) :-
    carry_on_id(CarryId),
    % collect all items except the carry-on
    findall(Id,(item(Id,_,_,_,_), Id \= CarryId), CheckedIds),
    compute_checked(CheckedIds,1,0,BagsTotal),
    ticket_fee(Ticket),
    Total is BagsTotal + Ticket.

% ---------------------------------- Query ----------------------------------------
:- total_cost(Total), format('Total cost: ~w~n', [Total]).
:- halt.