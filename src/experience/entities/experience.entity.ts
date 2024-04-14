import { Column, Entity, PrimaryGeneratedColumn } from 'typeorm';

@Entity('experience', { schema: 'public' })
export class Experience {
  @PrimaryGeneratedColumn({ type: 'integer', name: 'id' })
  id: number;

  @Column('integer', { name: 'level' })
  level: number;

  @Column('integer', { name: 'amount' })
  amount: number;
}
