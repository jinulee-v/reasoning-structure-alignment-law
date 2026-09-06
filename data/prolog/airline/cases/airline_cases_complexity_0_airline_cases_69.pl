/* ----------  Statutory rules needed for this case  ---------- */

% 1.  Base checked-bag fee for a Main-Cabin customer travelling
%     between Europe and the United States (Trans-Atlantic).
base_checked_fee(main_cabin,europe_us,1,0).
base_checked_fee(main_cabin,europe_us,2,100).
base_checked_fee(main_cabin,europe_us,3,200).
base_checked_fee(main_cabin,europe_us,N,200) :- N>=4.

% 2.  Oversize fees on Europe <-> U.S. flights
oversize_fee(Size,0)   :- Size =< 62.
oversize_fee(Size,30)  :- Size > 62, Size =< 65.
oversize_fee(Size,150) :- Size > 65, Size =< 115.
oversize_fee(Size,na)  :- Size > 115.           % not accepted (irrelevant here)

% 3.  Over-weight fees (all cabins / all regions for the weights we need)
overweight_fee(W,0)   :- W =< 50.
overweight_fee(W,30)  :- W > 50, W =< 53.
overweight_fee(W,100) :- W > 53, W =< 70.
overweight_fee(W,na)  :- W > 70.                % not accepted (irrelevant here)

% 4.  The higher of oversize / overweight applies (if either is 'na', bag rejected)
extra_fee(Size,W,Fee) :-
    oversize_fee(Size,Of),
    overweight_fee(W,Wf),
    max_fee(Of,Wf,Fee).

max_fee(na,_,na).
max_fee(_,na,na).
max_fee(A,B,A) :- A>=B.
max_fee(A,B,B) :- B>A.





% ----------  Facts describing John's flight and bags  ----------

cabin(main_cabin).
region(europe_us).
ticket_price(510).

% bag(Id, Length, Width, Height, Weight).
bag(1,19,14, 6,12).   % carry-on (no checked fee)
bag(2,42,26,15,53).
bag(3,49,37,26,62).
bag(4,35,19,10,51).
bag(5,37,21,10,53).

% ----------  Derived bag properties  ----------

bag_size(Id,Size) :-
    bag(Id,L,W,H,_),
    Size is L+W+H.

bag_weight(Id,W) :-
    bag(Id,_,_,_,W).

bag_extra_fee(Id,Fee) :-
    bag_size(Id,S),
    bag_weight(Id,W),
    extra_fee(S,W,Fee).

% Only bags 2-5 are checked; bag 1 is the free carry-on
checked_bag_ids([2,3,4,5]).

/* ----------  Cost of a particular ordering of the checked bags ---------- */

order_cost(Order,Cost) :-
    cabin(Cab), region(Reg),
    order_cost(Order,Cab,Reg,1,0,Cost).

order_cost([],_,_,_,Acc,Acc).
order_cost([Bag|Rest],Cab,Reg,Index,Acc0,Cost) :-
    base_checked_fee(Cab,Reg,Index,Base),
    bag_extra_fee(Bag,Extra),
    Fee is Base+Extra,
    Index1 is Index+1,
    Acc1 is Acc0+Fee,
    order_cost(Rest,Cab,Reg,Index1,Acc1,Cost).

/* ----------  Helper: permutations and min_list without external libraries ---------- */

perm([],[]).
perm(List,[H|Perm]) :-
    select(H,List,Rest),
    perm(Rest,Perm).

min_list([X|Xs],Min) :-
    min_list(Xs,X,Min).
min_list([],Min,Min).
min_list([H|T],Acc,Min) :-
    ( H<Acc -> Acc1=H ; Acc1=Acc ),
    min_list(T,Acc1,Min).

/* ----------  Minimal checked-bag cost (we try every ordering) ---------- */

min_checked_fee(Min) :-
    checked_bag_ids(Bags),
    findall(C,
            ( perm(Bags,Ord),
              order_cost(Ord,C)
            ),
            Costs),
    min_list(Costs,Min).

/* ----------  Total trip cost ---------- */

total_cost(Total) :-
    min_checked_fee(BagFees),
    ticket_price(Tix),
    Total is BagFees + Tix.

:- total_cost(Total), format('Total cost: ~w~n',[Total]).
:- halt.